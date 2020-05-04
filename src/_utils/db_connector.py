import logging
import os
import psycopg2

from typing import Callable, List, Tuple, TypeVar

logger = logging.getLogger('luigi-interface')

T = TypeVar('T')


class DbConnector:

    def __init__(self, host, user, database, password):
        super().__init__()
        self.host = host
        self.user = user
        self.database = database
        self.password = password

    def execute(self, *queries: List[str]) -> List[Tuple]:
        """
        Execute one or multiple queries as one atomic operation and returns
        the results of all queries. If any query fails, all will be reverted
        and an error will be raised.
        """
        return list(self._execute_queries(
            queries=queries,
            result_function=lambda cur: None
        ))

    def exists(self, query: str) -> bool:
        """
        Check if the given query returns any results. Return
        True if the query returns results, otherwise False.
        Note that the given query should absolutely not end on a semicolon.
        """
        return bool(self.query(
            query=f'SELECT EXISTS({query})',
            only_first=True)[0])

    def exists_table(self, table: str) -> bool:
        """
        Check if the given table is present in the database.
        """
        return self.exists(f'''
                SELECT * FROM information_schema.tables
                WHERE LOWER(table_name) = LOWER('{table}')
            ''')

    def query(self, query: str, only_first: bool = False) -> List[Tuple]:
        """
        Execute a query and return a list of results.
        If only_first is set to True, only return the
        first result as a tuple.
        """
        def result_function(cursor):
            nonlocal only_first
            if only_first:
                return cursor.fetchone()
            return cursor.fetchall()

        results = self._execute_query(
            query=query,
            result_function=result_function
        )
        result = next(results)
        if next(results, result) is not result:
            raise AssertionError(
                "DB access with just one query should only return one result")
        return result

    def query_with_header(self, query: str) -> List[Tuple]:
        """
        Execute a query and return two values of which the first is the list
        of fetched rows and the second is the list of column names.
        """
        all_results = self._execute_query(
            query=query,
            result_function=lambda cursor:
                (cursor.fetchall(), [desc[0] for desc in cursor.description])
        )
        results = next(all_results)
        if next(all_results, results) is not results:
            raise AssertionError(
                "DB access with just one query should only return one table")
        return results

    def _execute_queries(
                self,
                queries: List[str],
                result_function: Callable[[psycopg2.extensions.cursor], T]
            ) -> List[T]:
        """
        Executes all passed queries as one atomic operation and yields the
        results of each query. If any query fails, all will be reverted and an
        error will be raised.
        Note that this is a generator function so the operation will be only
        commited once the generator has been enumerated.
        """
        conn = psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password
        )
        try:
            with conn:
                with conn.cursor() as cur:
                    for query in queries:
                        logger.debug(f'Executing query: {query}')
                        cur.execute(query)
                        yield result_function(cur)
        finally:
            conn.close()

    def _execute_query(self, query: str, result_function: Callable) -> None:
        """
        Executes the passed query and returns the results.
        Note that this is a generator function so the operation will be only
        commited once the generator has been enumerated.
        """
        return self._execute_queries([query], result_function)


db_connector = DbConnector(
    host=os.environ['POSTGRES_HOST'],
    database=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'])
