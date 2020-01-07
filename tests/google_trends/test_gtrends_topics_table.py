from google_trends.gtrends_topics_table import *
from task_test import TaskTest

class TestGtrendsTopicsTable(TaskTest):
	def __init__(self, methodName):
		super().__init__(methodName)
		self.task = self.isolate(GTrendsTopicsTable())
	
	def test_getJson(self):
		self.task = GTrendsTopicsTable()
		actual = self.task.getJson()
		
		expected = [
			{'topic_id': '1', 'name': "one"},
			{'topic_id': '2', 'name': "two"}
		]
		self.assertEqual(actual, expected)

class TestGtrendsTopicsToDB(TaskTest):
	def test_topicsToDB(self):
		GtrendsTopicsToDB() # shouldnt raise

