import unittest
import json
import psycopg2
import os
import subprocess

""" 
IMPORTANT NOTE:
To be able to run tests that use this helper, you will need
* a running postgres database server
* a database named 'barberini_test'.
"""
# ------ CREATE DATABASE IF NECESSARY -------
conn = psycopg2.connect(
	host=os.environ['POSTGRES_HOST'],
	user=os.environ['POSTGRES_USER'],
	password=os.environ['POSTGRES_PASSWORD'],
	database=os.environ['POSTGRES_DB'])
try:
	conn.autocommit = True
	cur = conn.cursor()
	try:
		cur.execute("DROP DATABASE barberini_test;") # each test execution should get a fresh database
	except:
		pass
	cur.execute("CREATE DATABASE barberini_test;")
finally:
	conn.close()

class DatabaseHelper:
	def setUp(self):
		self.connection = psycopg2.connect(
			host=os.environ['POSTGRES_HOST'],
			dbname="barberini_test",
	    	user=os.environ['POSTGRES_USER'],
			password=os.environ['POSTGRES_PASSWORD'])
	
	def tearDown(self):
		self.connection.close()
	
	def request(self, query):
		self.cursor = self.connection.cursor()
		self.cursor.execute(query)
		self.result = cursor.fetchall()
		self.cursor.close()
		return result
	
	def commit(self, *queries):
		self.cursor = self.connection.cursor()
		for query in queries:
			cursor.execute(query)
		self.cursor.close()
		self.connection.commit()
	
	def column_names(self):
		self.cursor = self.connection.cursor()
		result = [self.cursor.desc[0] for desc in self.cursor.description]
		self.cursor.close()
		return result


class DatabaseTaskTest(unittest.TestCase):
	db = DatabaseHelper()
	
	def setUp(self):
		super().setUp()
		self.db.setUp()
		subprocess.call('cp -r tests_fake_files/. . --backup'.split())
	
	def tearDown(self):
		subprocess.call(['bash', '-c', 'find -iname *~ | awk \'{system("bash -c \'"\'"\'file="$1" bash -c \\"mv \\\\$file \\\\${file::-1}\\"\'"\'"\'")}\''])
		super().tearDown()
		self.db.tearDown()
	
	def isolate(self, task):
		task.complete = lambda: True
		return task
