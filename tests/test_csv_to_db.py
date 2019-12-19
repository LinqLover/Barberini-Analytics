import unittest
import psycopg2
import luigi
import time
import tempfile
import datetime
import pandas as pd
from unittest.mock import patch

from src._utils.csv_to_db import CsvToDb


# ------ DEFINE HELPERS -------

expected_data = [(1, 2, "abc", "xy,\"z"), (2, 10, "678", ",,;abc")]
expected_data_csv = "id,A,B,C\n1,2,abc,\"xy,\"\"z\"\n2,10,\"678\",\",,;abc\"\n"
tmp_csv_file = tempfile.NamedTemporaryFile()
with open(tmp_csv_file.name, "w") as fp:
    fp.write(expected_data_csv)

class DummyFileWrapper(luigi.Task):
    def output(self):
        return luigi.LocalTarget(tmp_csv_file.name)

class DummyWriteCsvToDb(CsvToDb):

    def __init__(self, table_name):
        super().__init__()
        self.__class__.table = table_name

        # By default luigi assigns the same task_id to the objects of this class.
        # That leads to errors when updating the marker table (tablue_updates).
        self.task_id = f"{self.task_id}_{str(datetime.datetime.now())}"

    columns = [
            ("id", "INT"),
            ("A", "INT"),
            ("B", "TEXT"),
            ("C", "TEXT")
    ]
    primary_key = "id"

    host = "host.docker.internal"
    database = "barberini_test"
    user = "postgres"
    password = "docker"

    table = None  # value set in __init__

    def requires(self):
        return DummyFileWrapper()

def get_temp_table():
    return f"tmp_{time.time()}".replace(".", "")


# -------- TESTS START HERE -------

class TestCsvToDb(unittest.TestCase):
    """ IMPORTANT: to be able to run this test you need to have a
            database barberini_test running"""

    # To test (by implementing subclasses):
    # - no duplicates are added
    # - column types are set as defined in the subclass
    
    @patch("src._utils.csv_to_db.set_db_connection_options")
    def test_adding_data_to_database_new_table(self, mock):

        # ----- Set up -------

        table_name = get_temp_table()
        dummy = DummyWriteCsvToDb(table_name)

        # ----- Execute code under test -----

        dummy.run()

        # ----- Inspect result -----

        mock.assert_called_once()

        con = psycopg2.connect(host="host.docker.internal", dbname="barberini_test",
                               user="postgres", password="docker")
        cur = con.cursor()
        cur.execute(f"select * from {table_name};")
        actual_data = cur.fetchall()
        cur.close()

        self.assertEqual(actual_data, expected_data)


        # ----- Delete the temporary table (if the test was successful) -------

        con.set_isolation_level(0)
        cur = con.cursor()
        cur.execute(f"DROP TABLE {table_name};")
        cur.close()
        con.close()

    @patch("src._utils.csv_to_db.set_db_connection_options")
    def test_adding_data_to_database_existing_table(self, mock):

        # ----- Set up -----

        table_name = get_temp_table()
        dummy = DummyWriteCsvToDb(table_name)

        con = psycopg2.connect(host="host.docker.internal", dbname="barberini_test",
                               user="postgres", password="docker")
        cur = con.cursor()
        cur.execute(f"CREATE TABLE {table_name} (id int, A int, B text, C text);")
        cur.execute(f"""
            ALTER TABLE {table_name} 
                ADD CONSTRAINT {table_name}_the_primary_key_constraint PRIMARY KEY (id);
        """)
        cur.execute(f"INSERT INTO {table_name} VALUES (0, 1, 'a', 'b');")
        cur.close()
        con.commit()

        # ----- Execute code under test ----
 
        dummy.run()
 
        # ----- Inspect result ------

        cur = con.cursor()
        cur.execute(f"select * from {table_name};")
        actual_data = cur.fetchall()
        cur.close()

        self.assertEqual(actual_data, [(0, 1, "a", "b"), *expected_data])


        # ----- Delete the temporary table -------

        con.set_isolation_level(0)
        cur = con.cursor()
        cur.execute(f"DROP TABLE {table_name};")
        cur.close()
        con.close()

    @patch("src._utils.csv_to_db.set_db_connection_options")
    def test_no_duplicates_are_inserted(self, mock):

        # ----- Set up -----

        table_name = get_temp_table()
        dummy = DummyWriteCsvToDb(table_name)

        con = psycopg2.connect(host="host.docker.internal", dbname="barberini_test",
                               user="postgres", password="docker")
        cur = con.cursor()
        cur.execute(f"CREATE TABLE {table_name} (id int, A int, B text, C text);")
        cur.execute(f"""
            ALTER TABLE {table_name} 
                ADD CONSTRAINT {table_name}_the_primary_key_constraint PRIMARY KEY (id);
        """)
        cur.execute(f"INSERT INTO {table_name} VALUES (1, 2, 'abc', 'xy,\"z');")
        cur.close()
        con.commit()

        # ----- Execute code under test ----
 
        dummy.run()
 
        # ----- Inspect result ------
        mock.assert_called_once()

        con = psycopg2.connect(host="host.docker.internal", dbname="barberini_test",
                               user="postgres", password="docker")
        cur = con.cursor()
        cur.execute(f"select * from {table_name};")
        actual_data = cur.fetchall()
        cur.close()

        self.assertEqual(actual_data, expected_data)


        # ----- Delete the temporary table (if the test was successful) -------

        con.set_isolation_level(0)
        cur = con.cursor()
        cur.execute(f"DROP TABLE {table_name};")
        cur.close()
        con.close()

