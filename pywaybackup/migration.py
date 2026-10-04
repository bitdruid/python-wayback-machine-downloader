"""
Schema migrations for snapshot databases written by older versions.

Only carries existing `.db` files forward, so an interrupted job can be resumed
after an update. Every step is tied to the version that made it necessary and
can be dropped once that version is out of use - nothing here is needed for a
database created by the current version.

    <= 4.x    waybackup_snapshots has no url_key
    <= 5.0.0  no job_id: waybackup_jobs is keyed by query_identifier and
              waybackup_snapshots.url_archive is unique across the whole file
"""

from sqlalchemy import MetaData, create_engine, event, inspect, text

from pywaybackup.Url import Url
from pywaybackup.Verbosity import Verbosity as vb

JOBS = "waybackup_jobs"
SNAPSHOTS = "waybackup_snapshots"


def migrate(url, metadata: MetaData, merge_www: bool = True):
    """
    Bring a database written by an older version up to the current schema.

    Runs before `create_all()`, which only creates missing tables and never
    alters existing ones. A no-op for new or current databases. Older versions
    only ever wrote SQLite files, so other backends are skipped entirely.

    Args:
        url: Database url of the engine about to be used.
        metadata (MetaData): The current models' metadata, used to create the
            rebuilt tables so the schema is defined in one place only.
        merge_www (bool): Needed to compute url_key exactly like the insert does.
    """
    engine = create_engine(url)
    try:
        if engine.dialect.name != "sqlite":
            return
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if JOBS not in tables or SNAPSHOTS not in tables:
            return
        job_columns = {c["name"] for c in inspector.get_columns(JOBS)}
        snapshot_columns = {c["name"] for c in inspector.get_columns(SNAPSHOTS)}
        if "job_id" in job_columns and "job_id" in snapshot_columns:
            return
    finally:
        engine.dispose()

    vb.write(content="\nMigrating database from an older version...")
    engine = _transactional_engine(url)
    try:
        with engine.begin() as conn:
            _migrate_job_id(conn, metadata, job_columns, snapshot_columns)
            if "url_key" not in snapshot_columns:
                _fill_url_key(conn, merge_www)
    finally:
        engine.dispose()


def _transactional_engine(url):
    """
    An engine on which DDL runs inside the transaction.

    pysqlite opens transactions on its own and only around DML, so the table
    renames and drops would be committed one by one. A crash halfway would leave
    a file that is neither the old nor the new schema. Taking over BEGIN makes
    the whole migration a single transaction (see the sqlalchemy sqlite docs,
    "Serializable isolation / Savepoints / Transactional DDL").
    """
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _no_implicit_transactions(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    return engine


def _migrate_job_id(conn, metadata: MetaData, job_columns: set, snapshot_columns: set):
    """
    <= 5.0.0: introduce job_id on both tables.

    SQLite can not drop the old primary key or the unique constraint on
    url_archive in place, so both tables are rebuilt: renamed away, recreated
    from the current models and copied over. Old indexes go with the old tables.

    The db file was already shared by every job on the same url, but the
    snapshot rows carried no owner. They are given to the most recently created
    job, which is the one that last wrote them. Any other job is rewound to
    re-insert its own rows when it is resumed.
    """
    conn.execute(text(f"ALTER TABLE {JOBS} RENAME TO {JOBS}_old"))
    conn.execute(text(f"ALTER TABLE {SNAPSHOTS} RENAME TO {SNAPSHOTS}_old"))
    metadata.tables[JOBS].create(conn)
    metadata.tables[SNAPSHOTS].create(conn)

    # rowid keeps the insertion order, so job_ids follow the order jobs were created in
    copy = sorted(job_columns - {"job_id"})
    conn.execute(
        text(f"INSERT INTO {JOBS} ({', '.join(copy)}) SELECT {', '.join(copy)} FROM {JOBS}_old ORDER BY rowid")
    )
    owner = conn.execute(text(f"SELECT max(job_id) FROM {JOBS}")).scalar()

    copy = sorted(snapshot_columns - {"job_id"})
    if owner is not None:
        conn.execute(
            text(
                f"INSERT INTO {SNAPSHOTS} (job_id, {', '.join(copy)}) "
                f"SELECT :owner, {', '.join(copy)} FROM {SNAPSHOTS}_old ORDER BY scid"
            ),
            {"owner": owner},
        )
        conn.execute(
            text(
                f"UPDATE {JOBS} SET insert_complete = NULL, index_complete = NULL, "
                f"filter_complete = NULL, query_progress = NULL WHERE job_id != :owner"
            ),
            {"owner": owner},
        )
    # the indexes were dropped with the old table and are only built while indexing
    conn.execute(text(f"UPDATE {JOBS} SET index_complete = NULL"))

    conn.execute(text(f"DROP TABLE {SNAPSHOTS}_old"))
    conn.execute(text(f"DROP TABLE {JOBS}_old"))


def _fill_url_key(conn, merge_www: bool, batch_size: int = 2500):
    """
    <= 4.x: compute url_key for every row, the same way the cdx insert does.
    """
    last_scid = 0
    while True:
        rows = conn.execute(
            text(f"SELECT scid, url_origin FROM {SNAPSHOTS} WHERE scid > :last ORDER BY scid LIMIT :n"),
            {"last": last_scid, "n": batch_size},
        ).all()
        if not rows:
            break
        keys = [{"scid": scid, "key": Url(origin, merge_www=merge_www).key} for scid, origin in rows if origin]
        if keys:
            conn.execute(text(f"UPDATE {SNAPSHOTS} SET url_key = :key WHERE scid = :scid"), keys)
        last_scid = rows[-1][0]
