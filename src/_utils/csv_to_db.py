import datetime as dt
import logging

import luigi
from luigi.contrib.postgres import CopyToTable
from psycopg2.errors import UndefinedTable

import db_connector
from data_preparation_task import minimal_mode

logger = logging.getLogger('luigi-interface')


class CsvToDb(CopyToTable):
    """
    Copies a depended csv file into the a central database.
    Subclasses have to override columns and requires().
    Don't forget to write a migration script if you change the table schema.
    """

    minimal_mode = luigi.parameter.BoolParameter(
        default=minimal_mode,
        description="If True, only a minimal amount of data will be prepared"
                    "in order to test the pipeline for structural problems")

    """
    Don't delete this! This parameter assures that every (sub)instance of me
    is treated as an individual and will be re-run.
    """
    dummy_date = luigi.FloatParameter(
        default=dt.datetime.timestamp(dt.datetime.now()))

    # override the default column separator (tab)
    column_separator = ','

    host = database = user = password = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set db connection parameters using env vars
        self.db_connector = db_connector.db_connector()
        self.host = self.db_connector.host
        self.database = self.db_connector.database
        self.user = self.db_connector.user
        self.password = self.db_connector.password
        self._columns = None  # lazy property

    seed = 666
    sql_file_path_pattern = 'src/_utils/sql_scripts/{0}.sql'

    @property
    def columns(self):
        if not self._columns:
            def fetch_columns():
                return self.db_connector.query(f'''
                    SELECT column_name, data_type
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE table_name = '{self.table}';
                ''')
            self._columns = fetch_columns()
            if not self._columns:
                raise UndefinedTable()

        return self._columns

    def copy(self, cursor, file):
        query = self.load_sql_script('copy', self.table, ','.join(
            [f'{col[0]} = EXCLUDED.{col[0]}' for col in self.columns]))
        logger.debug(f"{self.__class__}: Executing query: {query}")
        cursor.copy_expert(query, file)

    def create_table(self):
        """
        Overridden from superclass to forbid dynamical schema changes.
        """
        raise Exception(
            "CsvToDb does not support dynamical schema modifications."
            "To change the schema, create and run a migration script.")

    def rows(self):
        rows = super().rows()
        next(rows)
        return rows

    def load_sql_script(self, name, *args):
        with open(self.sql_file_path_pattern.format(name)) as sql_file:
            return sql_file.read().format(*args)
