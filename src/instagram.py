import json
import logging
import os

import luigi
import pandas as pd
from luigi.format import UTF8

from csv_to_db import CsvToDb
from data_preparation_task import DataPreparationTask
from facebook import try_request_multiple_times
from museum_facts import MuseumFacts

logger = logging.getLogger('luigi-interface')

# =============== ToDB Tasks ===============


class IgPostsToDB(CsvToDb):
    table = 'ig_post'

    columns = [
        ('ig_post_id', 'TEXT'),
        ('caption', 'TEXT'),
        ('timestamp', 'TIMESTAMP'),
        ('media_type', 'TEXT'),
        ('like_count', 'INT'),
        ('comments_count', 'INT'),
        ('permalink', 'TEXT')
    ]

    primary_key = 'ig_post_id'

    def requires(self):
        return FetchIgPosts()


class IgPostPerformanceToDB(CsvToDb):
    table = 'ig_post_performance'

    columns = [
        ()
    ]

    primary_key = ('ig_post_id', 'time_stamp')

    foreign_keys = [
        {
            'origin_column': 'ig_post_id',
            'target_table': 'ig_post',
            'target_column': 'ig_post_id'
        }
    ]


class IgProfileToDB(CsvToDb):
    table = 'ig_profile_metrics'

    columns = [
        ()
    ]

    primary_key = 'timestamp'

    def requires(self):
        return FetchIgProfile()

# =============== DataPreparation Tasks ===============


class FetchIgPosts(DataPreparationTask):
    def requires(self):
        return MuseumFacts()

    def output(self):
        return luigi.LocalTarget('output/instagram/ig_posts.csv', format=UTF8)

    def run(self):
        access_token = os.getenv('FB_ACCESS_TOKEN')
        if not access_token:
            logger.error("FB Access Token not set")
            raise EnvironmentError("FB Access token is not set")

        with self.input().open('r') as facts_file:
            facts = json.load(facts_file)
        page_id = facts['ids']['instagram']['pageId']

        all_media = []

        api_ver = 'v6.0'
        fields = [
            'id',
            'caption',
            'timestamp',
            'media_type',
            'like_count',
            'comments_count',
            'permalink'
        ]
        fields = ','.join(fields)
        limit = 100  # use limit=100 to keep amount of requests small

        media_url = (f'https://graph.facebook.com/{api_ver}/{page_id}/'
                     f'media?fields={fields}&limit={limit}')
        headers = {'Authorization': 'Bearer ' + access_token}

        res = try_request_multiple_times(media_url, headers=headers)
        res_json = res.json()

        current_count = len(res_json['data'])
        for media in res_json['data']:
            all_media.append(media)

        logger.info("Fetching Instagram posts ...")
        while 'next' in res_json['paging']:
            next_url = res_json['paging']['next']
            res = try_request_multiple_times(next_url, headers=headers)
            res_json = res.json()

            current_count += len(res_json['data'])
            print(
                f"\rFetched {current_count} Instagram posts",
                end='',
                flush=True)
            for media in res_json['data']:
                all_media.append(media)

            if os.getenv('MINIMAL', 'False') == 'True':
                print()  # have to manually print newline
                logger.info("Running in minimal mode, stopping now")
                res_json['paging'].pop('next')

        logger.info("Fetching of Instagram posts complete")

        df = pd.DataFrame([media for media in all_media])
        with self.output().open('w') as output_file:
            df.to_csv(output_file, index=False, header=True)


class FetchIgPostPerformance(DataPreparationTask):
    def requires(self):
        return MuseumFacts()

    def output(self):
        return luigi.LocalTarget(
            'output/instagram/ig_media_performance.csv',
            format=UTF8)

    def run(self):
        raise NotImplementedError


class FetchIgProfile(DataPreparationTask):
    def requires(self):
        return MuseumFacts()

    def output(self):
        return luigi.LocalTarget(
            'output/instagram/ig_profile.csv',
            format=UTF8)

    def run(self):
        raise NotImplementedError
