from sqlalchemy import (  # noqa: F401
    Column,
    Index,
    Integer,
    String,
    UniqueConstraint,
    and_,
    bindparam,
    create_engine,
    delete,
    func,
    insert,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional  # python 3.8
from pywaybackup.Verbosity import Verbosity as vb

Base = declarative_base()


class waybackup_job(Base):
    """
    SQLAlchemy ORM model for the 'waybackup_jobs' table.

    Stores metadata about backup jobs.

    Attributes:
        job_id (int): Surrogate primary key. Carried by every snapshot row.
        query_identifier (str): Unique identifier for the job, built from the args
            that define the underlying query (see PyWayBackup._query_identifier).
        query_progress (str): Progress of the job as a string (e.g., '5 / 10').
        insert_complete (int): Flag indicating if insertion is complete (1 or 0).
        index_complete (int): Flag indicating if indexing is complete (1 or 0).
        filter_complete (int): Flag indicating if filtering is complete (1 or 0).

    The surrogate key exists so snapshots reference the job by an integer instead of
    repeating the identifier string in every row and every index entry.
    """

    __tablename__ = "waybackup_jobs"

    job_id = Column(Integer, primary_key=True, autoincrement=True)
    query_identifier = Column(String, unique=True)
    query_progress = Column(String)
    insert_complete = Column(Integer)
    index_complete = Column(Integer)
    filter_complete = Column(Integer)


class waybackup_snapshots(Base):
    """
    SQLAlchemy ORM model for the 'waybackup_snapshots' table.

    Stores information about individual snapshots.

    Attributes:
        scid (int): Snapshot collection ID (primary key).
        job_id (int): Owning job (waybackup_jobs.job_id). Every query is scoped by it.
        counter (int): Counter for snapshot ordering or grouping.
        timestamp (str): Timestamp of the snapshot.
        url_archive (str): URL of the archived snapshot, unique within a job.
        url_origin (str): Original URL before archiving.
        url_key (str): Output path the url maps to, relative to the output dir (see Url.key).
        redirect_url (str): URL to which the original was redirected, if any.
        redirect_timestamp (str): Timestamp of the redirect, if applicable.
        response (str): HTTP response or status for the snapshot.
        file (str): Path to the file where the snapshot is stored.

    `url_archive` is unique per job rather than globally: two jobs on the same domain
    with different ranges overlap heavily, and the db file is already shared between
    them (its name derives from the url alone).
    """

    __tablename__ = "waybackup_snapshots"
    __table_args__ = (UniqueConstraint("job_id", "url_archive", name="uq_waybackup_snapshots_job_url"),)

    scid = Column(Integer, primary_key=True)
    job_id = Column(Integer, index=True)
    counter = Column(Integer)
    timestamp = Column(String)
    url_archive = Column(String)
    url_origin = Column(String)
    url_key = Column(String)
    redirect_url = Column(String)
    redirect_timestamp = Column(String)
    response = Column(String)
    file = Column(String)


class Database:
    """
    Database manager for waybackup jobs and snapshots.

    Handles job initialization, session management and operations
    not directly related to Snapshots or the Snapshot Collection class.

    Class Attributes:
        dbfile (str): Path to the SQLite database file.
        query_identifier (str): Identifier for the current job/query.
        job_id (int): Surrogate id of the current job, scoping every snapshot query.
        query_exist (bool): Whether the job already exists in the database.
        sessman (sessionmaker): SQLAlchemy session factory.
        query_progress (str): Progress string for the current job.
    """

    dbfile = None
    query_identifier = None
    job_id = None
    query_exist = False
    engine = None
    sessman = sessionmaker()
    query_progress = "0 / 0"

    @classmethod
    def init(cls, dbfile, query_identifier):
        """
        Initialize the database connection and resolve the job entry.

        Looks the job up by `query_identifier` and reuses its `job_id` if found,
        otherwise inserts a new job row. The resulting id scopes every snapshot
        query, so a db file shared by several jobs keeps them apart.

        Args:
            dbfile (str): Path to the SQLite database file.
            query_identifier (str): Unique identifier for the job/query.
        """
        cls.dbfile = dbfile
        cls.query_identifier = query_identifier
        cls.engine = create_engine(f"sqlite:///{dbfile}")
        cls.sessman = sessionmaker(bind=cls.engine)
        Base.metadata.create_all(cls.engine)

        db = Database(job_id=False)  # no job resolved yet
        job_id = db.session.execute(
            select(waybackup_job.job_id).where(waybackup_job.query_identifier == query_identifier)
        ).scalar_one_or_none()
        if job_id is not None:
            cls.query_exist = True
            cls.job_id = job_id
            db.job_id = job_id
            cls.query_progress = db.get_progress()
        else:
            result = db.session.execute(insert(waybackup_job).values(query_identifier=query_identifier))
            cls.job_id = result.inserted_primary_key[0]
            db.session.commit()
        db.close()

    @classmethod
    def close_engine(cls):
        """
        Dispose of the SQLAlchemy engine and release SQLite file handles.

        Required on Windows before the .db file can be deleted, since the OS
        holds an exclusive lock on open files. No-op on platforms where this
        isn't required, and idempotent if called more than once.
        """
        if cls.engine is not None:
            cls.engine.dispose()
            cls.engine = None

    def __init__(self, job_id=None):
        """
        Create a new session bound to a job.

        Args:
            job_id (int, optional): Job to scope queries to. Defaults to the job
                resolved by `init()`. `False` means "not resolved yet" and is only
                used by `init()` itself while looking the job up.
        """
        self.session = self.sessman()
        self.job_id = Database.job_id if job_id is None else job_id

    def close(self):
        """
        Try to commit any pending work; if that fails, rollback to avoid leaving open transactions
        """
        try:
            if self.session.in_transaction():
                vb.write(verbose="high", content="[Database.close] session in transaction: committing")
                try:
                    self.session.commit()
                    vb.write(verbose="high", content="[Database.close] commit successful")
                except Exception as e:
                    vb.write(verbose="high", content=f"[Database.close] commit failed: {e}; rolling back")
                    try:
                        self.session.rollback()
                        vb.write(verbose="high", content="[Database.close] rollback successful")
                    except Exception:
                        vb.write(verbose="high", content="[Database.close] rollback failed")
        finally:
            try:
                self.session.close()
                vb.write(verbose="high", content="[Database.close] session closed")
            except Exception as e:
                vb.write(verbose="high", content=f"[Database.close] session close failed: {e}")

    def write_progress(self, done: int, total: int):
        """
        Update the job's progress string in the database.

        Args:
            done (int): Number of completed items.
            total (int): Total number of items.
        """
        progress = f"{(done):,} / {(total):,}"
        self.session.execute(
            update(waybackup_job)
            .where(waybackup_job.job_id == self.job_id)
            .values(query_progress=progress)
        )
        self.session.commit()

    def get_progress(self) -> Optional[str]:
        """
        str or None: Progress string (e.g., '5 / 10') or None if not found.
        """
        return self.session.execute(
            select(waybackup_job.query_progress).where(waybackup_job.job_id == self.job_id)
        ).scalar_one_or_none()

    def get_insert_complete(self) -> Optional[int]:
        """
        int or None: 1 if complete, 0 if not, or None if not found.
        """
        return self.session.execute(
            select(waybackup_job.insert_complete).where(waybackup_job.job_id == self.job_id)
        ).scalar_one_or_none()

    def get_index_complete(self) -> Optional[int]:
        """
        int or None: 1 if complete, 0 if not, or None if not found.
        """
        return self.session.execute(
            select(waybackup_job.index_complete).where(waybackup_job.job_id == self.job_id)
        ).scalar_one_or_none()

    def get_filter_complete(self) -> Optional[int]:
        """
        int or None: 1 if complete, 0 if not, or None if not found.
        """
        return self.session.execute(
            select(waybackup_job.filter_complete).where(waybackup_job.job_id == self.job_id)
        ).scalar_one_or_none()

    def set_insert_complete(self):
        """
        Mark the job's insertion phase as complete in the database.
        """
        self.session.execute(
            update(waybackup_job)
            .where(waybackup_job.job_id == self.job_id)
            .values(insert_complete=1)
        )
        self.session.commit()

    def set_index_complete(self):
        """
        Mark the job's indexing phase as complete in the database.
        """
        self.session.execute(
            update(waybackup_job)
            .where(waybackup_job.job_id == self.job_id)
            .values(index_complete=1)
        )
        self.session.commit()

    def set_filter_complete(self):
        """
        Mark the job's filtering phase as complete in the database.
        """
        self.session.execute(
            update(waybackup_job)
            .where(waybackup_job.job_id == self.job_id)
            .values(filter_complete=1)
        )
        self.session.commit()
