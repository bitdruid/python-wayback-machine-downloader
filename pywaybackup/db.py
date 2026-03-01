from sqlalchemy import (
    Column,
    Index,
    Integer,
    String,
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
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Optional  # python 3.8
from pywaybackup.Verbosity import Verbosity as vb

Base = declarative_base()


class waybackup_job(Base):
    """
    SQLAlchemy ORM model for the 'waybackup_jobs' table.

    Stores metadata about backup jobs.

    Attributes:
        query_identifier (str): Unique identifier for the job (primary key).
        query_progress (str): Progress of the job as a string (e.g., '5 / 10').
        insert_complete (int): Flag indicating if insertion is complete (1 or 0).
        index_complete (int): Flag indicating if indexing is complete (1 or 0).
        filter_complete (int): Flag indicating if filtering is complete (1 or 0).
    """

    __tablename__ = "waybackup_jobs"

    query_identifier = Column(String, primary_key=True)
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
        counter (int): Counter for snapshot ordering or grouping.
        timestamp (str): Timestamp of the snapshot.
        url_archive (str): Unique URL of the archived snapshot.
        url_origin (str): Original URL before archiving.
        redirect_url (str): URL to which the original was redirected, if any.
        redirect_timestamp (str): Timestamp of the redirect, if applicable.
        response (str): HTTP response or status for the snapshot.
        file (str): Path to the file where the snapshot is stored.
    """

    __tablename__ = "waybackup_snapshots"

    scid = Column(Integer, primary_key=True)
    counter = Column(Integer)
    timestamp = Column(String)
    url_archive = Column(String, unique=True)
    url_origin = Column(String)
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
        query_exist (bool): Whether the job already exists in the database.
        sessman (sessionmaker): SQLAlchemy session factory.
        query_progress (str): Progress string for the current job.
    """

    dbfile = None
    query_identifier = None
    query_exist = False
    sessman = sessionmaker()
    query_progress = "0 / 0"

    @classmethod
    def init(cls, dbfile, query_identifier):
        """
        Initialize the database connection and ensure job entry exists.

        Args:
            dbfile (str): Path to the SQLite database file.
            query_identifier (str): Unique identifier for the job/query.
        """
        cls.dbfile = dbfile
        cls.query_identifier = query_identifier
        engine = create_engine(f"sqlite:///{dbfile}")
        cls.sessman = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)

        db = Database()
        if db.session.execute(
            select(waybackup_job.query_identifier).where(query_identifier == query_identifier)
        ).fetchone():
            cls.query_exist = True
            cls.query_progress = db.get_progress()
        else:
            db.session.execute(insert(waybackup_job).values(query_identifier=query_identifier))
        db.close()

    def __init__(self):
        """
        Create a new session.
        """
        self.session = self.sessman()

    def close(self):
        """
        Try to commit any pending work; if that fails, rollback to avoid leaving open transactions
        """
        try:
            if self.session.in_transaction():
                vb.write(verbose=True, content=f"[Database.close] session in transaction: committing")
                try:
                    self.session.commit()
                    vb.write(verbose=True, content=f"[Database.close] commit successful")
                except Exception as e:
                    vb.write(verbose=True, content=f"[Database.close] commit failed: {e}; rolling back")
                    try:
                        self.session.rollback()
                        vb.write(verbose=True, content=f"[Database.close] rollback successful")
                    except Exception:
                        vb.write(verbose=True, content=f"[Database.close] rollback failed")
        finally:
            try:
                self.session.close()
                vb.write(verbose=True, content=f"[Database.close] session closed")
            except Exception as e:
                vb.write(verbose=True, content=f"[Database.close] session close failed: {e}")

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
            .where(waybackup_job.query_identifier == self.query_identifier)
            .values(query_progress=progress)
        )
        self.session.commit()

    def get_progress(self) -> Optional[str]:
        """
        str or None: Progress string (e.g., '5 / 10') or None if not found.
        """
        return self.session.execute(
            select(waybackup_job.query_progress).where(waybackup_job.query_identifier == self.query_identifier)
        ).scalar_one_or_none()

    def get_insert_complete(self) -> Optional[int]:
        """
        int or None: 1 if complete, 0 if not, or None if not found.
        """
        return self.session.execute(
            select(waybackup_job.insert_complete).where(waybackup_job.query_identifier == self.query_identifier)
        ).scalar_one_or_none()

    def get_index_complete(self) -> Optional[int]:
        """
        int or None: 1 if complete, 0 if not, or None if not found.
        """
        return self.session.execute(
            select(waybackup_job.index_complete).where(waybackup_job.query_identifier == self.query_identifier)
        ).scalar_one_or_none()

    def get_filter_complete(self) -> Optional[int]:
        """
        int or None: 1 if complete, 0 if not, or None if not found.
        """
        return self.session.execute(
            select(waybackup_job.filter_complete).where(waybackup_job.query_identifier == self.query_identifier)
        ).scalar_one_or_none()

    def set_insert_complete(self):
        """
        Mark the job's insertion phase as complete in the database.
        """
        self.session.execute(
            update(waybackup_job)
            .where(waybackup_job.query_identifier == self.query_identifier)
            .values(insert_complete=1)
        )
        self.session.commit()

    def set_index_complete(self):
        """
        Mark the job's indexing phase as complete in the database.
        """
        self.session.execute(
            update(waybackup_job)
            .where(waybackup_job.query_identifier == self.query_identifier)
            .values(index_complete=1)
        )
        self.session.commit()

    def set_filter_complete(self):
        """
        Mark the job's filtering phase as complete in the database.
        """
        self.session.execute(
            update(waybackup_job)
            .where(waybackup_job.query_identifier == self.query_identifier)
            .values(filter_complete=1)
        )
        self.session.commit()
