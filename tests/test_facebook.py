import datetime as dt
import json
import unittest
from unittest.mock import MagicMock, patch

from luigi.format import UTF8
from luigi.mock import MockTarget
from requests.exceptions import HTTPError

import facebook


class TestFacebookPost(unittest.TestCase):

    @patch('facebook.requests.get')
    @patch.object(facebook.FetchFbPosts, 'output')
    @patch.object(facebook.MuseumFacts, 'output')
    def test_post_transformation(self,
                                 fact_mock,
                                 output_mock,
                                 requests_get_mock):
        fact_target = MockTarget('facts_in', format=UTF8)
        fact_mock.return_value = fact_target
        output_target = MockTarget('post_out', format=UTF8)
        output_mock.return_value = output_target

        with open('tests/test_data/facebook/post_actual.json',
                  'r',
                  encoding='utf-8') as data_in:
            input_data = data_in.read()

        with open('tests/test_data/facebook/post_expected.csv',
                  'r',
                  encoding='utf-8') as data_out:
            expected_data = data_out.read()

        # Overwrite requests 'get' return value to provide our test data
        def mock_json():
            return json.loads(input_data)

        mock_response = MagicMock(ok=True, json=mock_json)
        requests_get_mock.return_value = mock_response

        facebook.MuseumFacts().run()
        facebook.FetchFbPosts().run()

        with output_target.open('r') as output_data:
            self.assertEqual(output_data.read(), expected_data)

    @patch('facebook.requests.get')
    @patch.object(facebook.FetchFbPosts, 'output')
    @patch.object(facebook.MuseumFacts, 'output')
    def test_pagination(self, fact_mock, output_mock, requests_get_mock):
        fact_target = MockTarget('facts_in', format=UTF8)
        fact_mock.return_value = fact_target
        output_target = MockTarget('post_out', format=UTF8)
        output_mock.return_value = output_target

        with open('tests/test_data/facebook/post_next.json', 'r') \
                as next_data_in:
            next_data = next_data_in.read()

        with open('tests/test_data/facebook/post_previous.json', 'r') \
                as previous_data_in:
            previous_data = previous_data_in.read()

        def next_json():
            return json.loads(next_data)

        def previous_json():
            return json.loads(previous_data)

        next_response = MagicMock(ok=True, json=next_json)
        previous_response = MagicMock(ok=True, json=previous_json)

        requests_get_mock.side_effect = [
            next_response,
            previous_response
        ]

        facebook.MuseumFacts().run()
        facebook.FetchFbPosts().run()

        self.assertEqual(requests_get_mock.call_count, 2)

    @patch('facebook.requests.get')
    @patch.object(facebook.MuseumFacts, 'output')
    def test_invalid_response_raises_error(self,
                                           fact_mock,
                                           requests_get_mock):
        fact_target = MockTarget('facts_in', format=UTF8)
        fact_mock.return_value = fact_target
        error_mock = MagicMock(status_code=404)

        def error_raiser():
            return facebook.requests.Response.raise_for_status(error_mock)

        mock_response = MagicMock(
            raise_for_status=error_raiser)

        requests_get_mock.return_value = mock_response

        facebook.MuseumFacts().run()

        with self.assertRaises(HTTPError):
            facebook.FetchFbPosts().run()


class TestFacebookPostPerformance(unittest.TestCase):

    @patch('facebook.requests.get')
    @patch.object(facebook.FetchFbPostPerformance, 'output')
    @patch.object(facebook.FetchFbPostPerformance, 'input')
    def test_post_performance_transformation(self,
                                             input_mock,
                                             output_mock,
                                             requests_get_mock):

        input_target = MockTarget('posts_in', format=UTF8)
        input_mock.return_value = input_target
        output_target = MockTarget('insights_out', format=UTF8)
        output_mock.return_value = output_target

        with input_target.open('w') as posts_target:
            with open('tests/test_data/facebook/post_expected.csv',
                      'r',
                      encoding='utf-8') as posts_input:
                posts_target.write(posts_input.read())

        with open('tests/test_data/facebook/post_insights_actual.json',
                  'r',
                  encoding='utf-8') as json_in:
            input_insights = json_in.read()

        def mock_json():
            return json.loads(input_insights)

        mock_response = MagicMock(ok=True, json=mock_json)
        requests_get_mock.return_value = mock_response

        class MockDatetime(dt.datetime):
            @classmethod
            def now(cls):
                return cls(2020, 1, 1, 0, 0, 5)

        facebook.dt.datetime = MockDatetime

        facebook.FetchFbPostPerformance().run()

        with open('tests/test_data/facebook/post_insights_expected.csv',
                  'r',
                  encoding='utf-8') as csv_out:
            expected_insights = csv_out.read()

        with output_target.open('r') as output_data:
            self.assertEqual(output_data.read(), expected_insights)

    @patch('facebook.requests.get')
    @patch.object(facebook.FetchFbPostPerformance, 'output')
    @patch.object(facebook.FetchFbPostPerformance, 'input')
    def test_post_performance_edge_cases(self,
                                         input_mock,
                                         output_mock,
                                         requests_get_mock):
        input_target = MockTarget('posts_in', format=UTF8)
        input_mock.return_value = input_target
        output_target = MockTarget('insights_out', format=UTF8)
        output_mock.return_value = output_target

        with input_target.open('w') as posts_target:
            with open('tests/test_data/facebook/post_expected.csv',
                      'r',
                      encoding='utf-8') as posts_input:
                posts_target.write(posts_input.read())

        with open('tests/test_data/facebook/post_insights_edgecases.json',
                  'r',
                  encoding='utf-8') as json_in:
            edge_insights = json_in.read()

        def mock_json():
            return json.loads(edge_insights)

        mock_response = MagicMock(ok=True, json=mock_json)
        requests_get_mock.return_value = mock_response

        # The current edge case test data should cause the interpretation to
        # fail at a very specific point (processing "react_anger")
        with self.assertRaises(ValueError) as cm:
            facebook.FetchFbPostPerformance().run()

        error = cm.exception
        self.assertEqual(str(error),
                         'invalid literal for int() with base 10: \'4.4\'')
