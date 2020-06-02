from abc import abstractmethod
import datetime as dt
import json
import logging
import os

import luigi
import pandas as pd
import requests
from luigi.format import UTF8

from csv_to_db import CsvToDb
from data_preparation import DataPreparationTask
from museum_facts import MuseumFacts

logger = logging.getLogger('luigi-interface')

API_VER = 'v6.0'
API_BASE = f'https://graph.facebook.com/{API_VER}'

# ======= ToDB Tasks =======


class FbPostsToDB(CsvToDb):

    table = 'fb_post'

    def requires(self):
        return FetchFbPosts()


class FbPostPerformanceToDB(CsvToDb):

    table = 'fb_post_performance'

    def requires(self):
        return FetchFbPostPerformance(table=self.table)


class FbPostCommentsToDB(CsvToDb):

    table = 'fb_post_comment'

    def requires(self):
        return FetchFbPostComments(table=self.table)

# ======= FetchTasks =======


class FetchFbPosts(DataPreparationTask):

    def requires(self):
        return MuseumFacts()

    def output(self):
        return luigi.LocalTarget(
            f'{self.output_dir}/facebook/fb_posts.csv', format=UTF8)

    def run(self):
        with self.input().open('r') as facts_file:
            facts = json.load(facts_file)
        page_id = facts['ids']['facebook']['pageId']

        posts = self.fetch_posts(page_id)
        df = self.transform_posts(posts)

        with self.output().open('w') as output_file:
            df.to_csv(output_file, index=False, header=True)

    def fetch_posts(self, page_id):
        limit = 100
        url = f'{API_BASE}/{page_id}/published_posts?limit={limit}'

        response = try_request_multiple_times(url)
        response_content = response.json()
        yield from response_content['data']

        # log_loop = self.loop_verbose(msg="Fetching facebook page {index}")
        # This is currently buggy as it only prints out every second iteration
        # Replaced with logger.info for now (TODO: Fix loop_verbose)
        i = 1
        while 'next' in response_content['paging']:
            logger.info(f"Fetched approx. {i * limit} Facebook posts")
            i += 1
            url = response_content['paging']['next']

            # next(log_loop)
            response = try_request_multiple_times(url)
            response_content = response.json()
            yield from response_content['data']

            if self.minimal_mode:
                response_content['paging'].pop('next')

        logger.info("Fetching of facebook posts completed")

    def transform_posts(self, posts):
        df = pd.DataFrame(posts)
        fb_post_ids = df['id'].str.split('_', n=1, expand=True)
        df = df.filter(['created_time', 'message'])
        df = fb_post_ids.join(df)
        df.columns = ['page_id', 'post_id', 'post_date', 'text']
        return df


class FetchFbPostDetails(DataPreparationTask):
    """
    This abstract class encapsulates common behavior for tasks
    such as FetchFbPostPerformance and FetchFbPostComments
    """
    timespan = luigi.parameter.TimeDeltaParameter(
        default=dt.timedelta(days=60),
        description="For how much time posts should be fetched")

    # Override the default timeout of 10 minutes to allow
    # FetchFbPostPerformance to take up to 20 minutes.
    worker_timeout = 1200

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimum_relevant_date = dt.datetime.now() - self.timespan

    def _requires(self):
        return luigi.task.flatten([
            FbPostsToDB(),
            super()._requires()
        ])

    def requires(self):
        return FetchFbPosts()

    @abstractmethod
    def output(self):
        pass

    @abstractmethod
    def run(self):
        pass

    @staticmethod
    def post_date(df, index):
        return dt.datetime.strptime(
            df['post_date'][index],
            '%Y-%m-%dT%H:%M:%S+%f')


class FetchFbPostPerformance(FetchFbPostDetails):

    def output(self):
        return luigi.LocalTarget(
            f'{self.output_dir}/facebook/fb_post_performances.csv',
            format=UTF8)

    def run(self):
        current_timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        performances = []
        with self.input().open('r') as csv_in:
            df = pd.read_csv(csv_in)

        if self.minimal_mode:
            df = df.head(5)

        invalid_count = 0
        for index in self.iter_verbose(
                df.index,
                msg="Fetching performance data for FB post {index}/{size}"):
            page_id, post_id = \
                str(df['page_id'][index]), str(df['post_id'][index])
            fb_post_id = f'{page_id}_{post_id}'
            post_date = self.post_date(df, index)
            if post_date < self.minimum_relevant_date:
                continue

            logger.debug(
                f"Loading performance data for FB post {fb_post_id}")

            metrics = ','.join([
                'post_reactions_by_type_total',
                'post_activity_by_action_type',
                'post_clicks_by_type',
                'post_negative_feedback',
                'post_impressions_paid',
                'post_impressions',
                'post_impressions_unique'  # "reach"
            ])
            url = f'{API_BASE}/{fb_post_id}/insights?metric={metrics}'

            response = try_request_multiple_times(url)

            if response.status_code == 400:
                invalid_count += 1
                continue
            response.raise_for_status()  # in case of another error
            response_content = response.json()

            post_perf = {
                'timestamp': current_timestamp,
            }

            # Reactions
            reactions = response_content['data'][0]['values'][0]['value']
            post_perf['react_like'] = int(reactions.get('like', 0))
            post_perf['react_love'] = int(reactions.get('love', 0))
            post_perf['react_wow'] = int(reactions.get('wow', 0))
            post_perf['react_haha'] = int(reactions.get('haha', 0))
            post_perf['react_sorry'] = int(reactions.get('sorry', 0))
            post_perf['react_anger'] = int(reactions.get('anger', 0))

            # Activity
            activity = response_content['data'][1]['values'][0]['value']
            post_perf['likes'] = int(activity.get('like', 0))
            post_perf['shares'] = int(activity.get('share', 0))
            post_perf['comments'] = int(activity.get('comment', 0))

            # Clicks
            clicks = response_content['data'][2]['values'][0]['value']
            post_perf['video_clicks'] = int(clicks.get('video play', 0))
            post_perf['link_clicks'] = int(clicks.get('link clicks', 0))
            post_perf['other_clicks'] = int(clicks.get('other clicks', 0))

            # negative feedback (only one field)
            post_perf['negative_feedback'] = \
                response_content['data'][3]['values'][0]['value']

            # number of times the post entered a person's screen through
            # paid distribution such as an ad
            post_perf['paid_impressions'] = \
                response_content['data'][4]['values'][0]['value']

            post_perf['post_impressions'] = \
                response_content['data'][5]['values'][0]['value']

            post_perf['post_impressions_unique'] = \
                response_content['data'][6]['values'][0]['value']

            post_perf.update(
                page_id=page_id,
                post_id=post_id
            )
            performances.append(post_perf)
        if invalid_count:
            logger.warning(f"Skipped {invalid_count} posts")

        df = pd.DataFrame(performances)

        # For some reason, all except the first set of performance
        # values get inserted twice into the performances list.
        # This could be due to a bug in iter_verbose, though it's uncertain.
        # TODO: Investigate and fix the root cause, this is a workaround
        df.drop_duplicates(subset='post_id', inplace=True, ignore_index=True)

        df = self.filter_fkey_violations(df)
        df = self.condense_performance_values(df)

        with self.output().open('w') as output_file:
            df.to_csv(output_file, index=False, header=True)


class FetchFbPostComments(FetchFbPostDetails):

    def output(self):
        return luigi.LocalTarget(
            f'{self.output_dir}/facebook/fb_post_comments.csv',
            format=UTF8)

    def run(self):
        with self.input().open() as fb_post_file:
            df = pd.read_csv(fb_post_file)
        comments = []

        if self.minimal_mode:
            df = df.head(5)

        comments = self.fetch_comments(df)
        df = pd.DataFrame(comments)

        # Posts can appear multiple times, causing comments to
        # be fetched multiple times as well, causing
        # primary key violations
        # See #227
        df = df.drop_duplicates(
            subset=['comment_id', 'post_id'], ignore_index=True)
        df = df.astype({
            'post_id': str,
            'comment_id': str,
            'page_id': str
        })

        # only convert 'response_to' to string if it exists,
        # since otherwise it would result in a string "None"
        df['response_to'] = df['response_to'].apply(
            lambda x: str(x) if x else None)

        df = self.filter_fkey_violations(df)

        with self.output().open('w') as output_file:
            df.to_csv(output_file, index=False, header=True)

    def fetch_comments(self, df):
        invalid_count = 0

        # Handle each post
        for i in df.index:
            page_id, post_id = df['page_id'][i], df['post_id'][i]
            fb_post_id = f'{page_id}_{post_id}'
            post_date = self.post_date(df, i)
            if post_date < self.minimum_relevant_date:
                continue

            # Grab up to 100 comments for the post (maximum)
            limit = 100

            # 'toplevel' or 'stream' (toplevel doesn't include replies)
            # Using 'toplevel' here allows us to safely
            # set parent to None for all comments returned
            # by the first query
            filt = 'toplevel'

            # 'chronological' or 'reverse_chronolocial'
            order = 'chronological'

            fields = ','.join([
                'id',
                'created_time',
                'comment_count',
                'message',
                'comments'
                ])

            url = (f'{API_BASE}/{fb_post_id}/comments?limit={limit}'
                   f'filter={filt}&order={order}&fields={fields}')

            response = try_request_multiple_times(url)
            if response.status_code == 400:
                invalid_count += 1
                continue
            response_data = response.json().get('data')

            logger.info(f"Fetched {len(response_data)} "
                        f"comments for post {post_id}")

            # Handle each comment for the post
            for comment in response_data:
                comment_id = comment.get('id').split('_')[1]

                yield {
                    'post_id': str(post_id),
                    'comment_id': str(comment_id),
                    'page_id': str(page_id),
                    'post_date': comment.get('created_time'),
                    'text': comment.get('message'),
                    'is_from_museum': self.from_barberini(comment),
                    'response_to': None
                }

                if comment.get('comment_count'):
                    try:
                        # Handle each reply for the comment
                        for reply in comment['comments']['data']:
                            yield {
                                'comment_id': reply.get('id').split('_')[1],
                                'page_id': str(page_id),
                                'post_id': str(post_id),
                                'post_date': reply.get('created_time'),
                                'text': reply.get('message'),
                                'is_from_museum': self.from_barberini(reply),
                                'response_to': str(comment_id)
                            }
                    except KeyError:
                        # Sometimes, replies become unavailable. In this case,
                        # the Graph API returns the true 'comment_count',
                        # but does not provide a 'comments' field anyway
                        logger.warning(
                            f"Failed to retrieve replies for comment "
                            f"{comment.get('id')}")

        if invalid_count:
            logger.warning(f"Skipped {invalid_count} posts")

    @staticmethod
    def from_barberini(comment_json):
        return comment_json.get('from', {}) \
           .get('name') == 'Museum Barberini'


def try_request_multiple_times(url, **kwargs):
    """
    Not all requests to the facebook api are successful. To allow
    some requests to fail (mainly: to time out), request the api up
    to four times.
    """
    headers = kwargs.pop('headers', None)
    if not headers:
        access_token = os.getenv('FB_ACCESS_TOKEN')
        if not access_token:
            raise EnvironmentError("FB Access token is not set")
        headers = {'Authorization': 'Bearer ' + access_token}

    for _ in range(3):
        try:
            response = requests.get(
                url,
                timeout=60,
                headers=headers,
                **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(
                "An Error occurred requesting the Facebook API.\n"
                "Trying to request the API again.\n"
                f"Error message: {e}"
            )
    response = requests.get(url, timeout=100, headers=headers, **kwargs)

    # cause clear error instead of trying
    # to process the invalid response
    # (except if we tried to access a foreign object)
    if not response.ok and not response.status_code == 400:
        response.raise_for_status()
    return response
