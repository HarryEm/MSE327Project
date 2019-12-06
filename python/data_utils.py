import requests
import random
from glob import glob
import pandas as pd
import os
import re
from statistics import mean
import datetime
import time

# Features used for the merge_csv_file function
FEATURES_TO_EXTRACT = ['blurb', 'category', 'country', 'created_at', 'deadline', 'id', 'launched_at', 'name',
                       'slug', 'state', 'usd_pledged', 'static_usd_rate', 'goal', 'urls']

FEATURES = ['blurb', 'category', 'country', 'created_at', 'deadline', 'id', 'launched_at', 'name',
            'slug', 'state', 'usd_pledged', 'usd_goal', 'project_url', 'reward_url']

# Mapping for the pre_processing_data function
CATEGORY_MAPPING = {'Art': 0,
                    'Comics': 1,
                    'Crafts': 2,
                    'Dance': 3,
                    'Design': 4,
                    'Fashion': 5,
                    'Film & Video': 6,
                    'Food': 7,
                    'Games': 8,
                    'Journalism': 9,
                    'Music': 10,
                    'Photography': 11,
                    'Publishing': 12,
                    'Technology': 13,
                    'Theater': 14}

STATE_MAPPING = {'failed': 0, 'successful': 1}

COUNTRY_MAPPING = {'US': 0,
                   'MX': 1,
                   'NZ': 2,
                   'CA': 3,
                   'CH': 4,
                   'HK': 5,
                   'GB': 6,
                   'ES': 7,
                   'JP': 8,
                   'AU': 9,
                   'FR': 10,
                   'DE': 11,
                   'NL': 12,
                   'SE': 13,
                   'IT': 14,
                   'AT': 15,
                   'DK': 16,
                   'NO': 17,
                   'SG': 18,
                   'IE': 19,
                   'BE': 20,
                   'LU': 21}


def merge_csv_file(data_folder, output_file):
    data = glob(data_folder + '/*/*csv', recursive=False)
    n = len(data)

    df = pd.DataFrame(columns=FEATURES)
    df = df.reindex(sorted(df.columns), axis=1)

    df.to_csv(output_file, index=False, header=True, sep=',')

    temp_file = '_temp.'.join(output_file.split('.'))

    for i, csv_file in enumerate(data):
        print('PROGRESS......................{: 5.1f}%'.format(i * 100 / n))
        temp_df = pd.read_csv(csv_file)[FEATURES_TO_EXTRACT]

        temp_df = temp_df[(temp_df['state'] == 'successful') | (temp_df['state'] == 'failed')]

        temp_df['reward_url'] = list(map(lambda e: eval(str(e))['web']['rewards'], temp_df['urls']))
        temp_df['project_url'] = list(map(lambda e: eval(str(e))['web']['project'], temp_df['urls']))
        temp_df.drop(['urls'], axis=1, inplace=True)

        temp_df['usd_goal'] = temp_df['static_usd_rate'] * temp_df['goal']

        temp_df['category'] = list(map(lambda e: re.findall(r'https?://www.kickstarter.com/.*categories/([^/"}]*).*$',
                                                            str(e))[0].title(),
                                       temp_df['category']))
        temp_df['category'] = list(map(lambda e: re.sub(r'%20', ' ', str(e)), temp_df['category']))

        temp_df.drop(['static_usd_rate', 'goal'], axis=1, inplace=True)

        temp_df.drop_duplicates(inplace=True)
        temp_df = temp_df.reindex(sorted(temp_df.columns), axis=1)

        temp_df.to_csv(temp_file, index=False, header=False, sep=',')
        with open(temp_file, 'r') as f:
            text = f.read()

        with open(output_file, 'a') as f:
            f.write(text)

        if i % 50 == 0:
            df = pd.read_csv(output_file)
            df.drop_duplicates(inplace=True)
            df.to_csv(output_file, header=True, index=False)

    os.remove(temp_file)

    df = pd.read_csv(output_file)
    df.drop_duplicates(inplace=True)
    df.to_csv(output_file, header=True, index=False)


def collect_campaign_info(url, data):
    response = requests.get(url)
    page_data = response.text

    if re.findall(r'are sending too many requests', page_data, re.DOTALL):
        return data, 0
    elif re.findall(
            r'been hidden for privacy.*?This project has been removed from visibility at the request of the creator',
            page_data, re.DOTALL):
        return data, 1
    elif re.findall(r'currently unavailable', page_data, re.DOTALL):
        return data, 1
    elif re.findall(r'this project is no longer available', page_data, re.DOTALL):
        return data, 1
    else:
        rewards = re.findall(r'About <span>.*?\$.*?([0-9,]+)</span>.*?pledge__reward-description.*?<p>(.*?)</p>',
                             page_data, re.DOTALL)
        reward_levels = list(map(lambda x: int(re.sub(r',', '', x[0])), rewards))
        reward_descriptions = list(map(lambda x: len(x[1]), rewards))

        try:
            faq = re.findall(r'projectFAQsCount&quot;:([0-9,]+),', page_data, re.DOTALL)[0]
        except IndexError:
            faq = re.findall(r'FAQ.*?<span class="count">([0-9,]+)</span>', page_data, re.DOTALL)[0]
        faq = re.sub(r',', '', faq)
        data['project_url'].append(url)
        data['rewards_levels'].append(len(reward_levels))
        data['rewards_min'].append(min(reward_levels))
        data['rewards_max'].append(max(reward_levels))
        data['rewards_mean'].append(int(mean(reward_levels)))
        data['has_1dollar_reward'].append(int(1 in reward_levels))
        data['avg_reward_description'].append(int(mean(reward_descriptions)))

        data['faq'].append(int(faq))

        data['is_project_we_love'].append(int(bool(re.match(r'.*Project We Love.*', page_data, re.DOTALL))))

        return data, 1


def add_campaign_info(data_file, output_file, max_request=250):
    df = pd.read_csv(data_file)

    project_urls = list(df[df['data_status'] == 0]['project_url'].values)
    random.shuffle(project_urls)

    campaign_data = {'project_url': [], 'rewards_levels': [], 'rewards_min': [], 'rewards_max': [], 'rewards_mean': [],
                     'has_1dollar_reward': [], 'avg_reward_description': [], 'faq': [], 'is_project_we_love': []}

    for i, project_url in enumerate(project_urls):
        print('PROGRESS......................{:04d}'.format(i))
        print(project_url)
        campaign_data, status = collect_campaign_info(project_url, campaign_data)
        time.sleep(0.2)
        if status == 0:
            break

        if i > max_request:
            break

    campaign_df = pd.DataFrame.from_dict(campaign_data)

    collected_url = {e: 0 for e in campaign_df['project_url'].values}
    updated_projects = [u in collected_url for u in df['project_url'].values]

    df.loc[updated_projects, 'data_status'] = 1
    df.to_csv(data_file, header=True, index=False)

    df_update = pd.merge(df, campaign_df, on='project_url', how='inner')
    df_final = pd.read_csv(output_file)
    df_final = pd.concat([df_final, df_update], sort=True)
    df_final.drop(['data_status'], axis=1, inplace=True)
    df_final.to_csv(output_file, header=True, index=False)

    print('DONE')


def is_asking_for_help(blurb):
    if re.match(r'\bplease\b', str(blurb).lower()) or re.match(r'\bhelp us\b', str(blurb).lower()):
        if re.match(r'\bsupport\b', str(blurb).lower()):
            return 1
        elif re.match(r'\bhelp\b', str(blurb).lower()):
            return 1
        elif re.match(r'\bdonate\b', str(blurb).lower()):
            return 1
        elif re.match(r'\bbe a part of\b', str(blurb).lower()):
            return 1
        else:
            return 0
    elif re.match(r'\bhelp us\b', str(blurb).lower()):
        return 1
    else:
        return 0


def pre_processing_data(data_file, output_file):
    df = pd.read_csv(data_file)
    time_origin = datetime.datetime(1970, 1, 1)
    df['deadline'] = list(map(lambda t: (datetime.datetime.fromtimestamp(t)-time_origin).days,
                              df['deadline'].values))
    df['launched_at'] = list(map(lambda t: (datetime.datetime.fromtimestamp(t)-time_origin).days,
                                 df['launched_at'].values))

    df['duration'] = [df['deadline'][i] - df['launched_at'][i] for i in range(len(df['launched_at']))]
    df['duration'] = list(map(lambda x: int(x), df['duration'].values))

    df['is_asking_for_help'] = list(map(lambda x: is_asking_for_help(x), df['blurb'].values))
    df['blurb_length'] = list(map(lambda x: len(str(x)), df['blurb'].values))
    df['blurb_word_count'] = list(map(lambda x: len(str(x).split(' ')), df['blurb'].values))

    df['name_length'] = list(map(lambda x: len(str(x)), df['name'].values))

    df['state'] = list(map(lambda x: STATE_MAPPING[str(x)], df['state'].values))

    for category in CATEGORY_MAPPING:
        col_name = 'category_{}'.format(category.lower())
        col_name = re.sub(r'[^a-zA-Z]', ' ', col_name.strip())
        col_name = re.sub(r'\s+', '_', col_name)
        df[col_name] = list(map(lambda x: int(x == category), df['category'].values))

    df['has_faq'] = list(map(lambda x: int(x > 0), df['faq'].values))

    for country in COUNTRY_MAPPING:
        col_name = 'country_{}'.format(country.lower())
        df[col_name] = list(map(lambda x: int(x == country), df['country'].values))

    df.drop(['blurb', 'created_at', 'deadline', 'id', 'launched_at', 'name', 'project_url',
             'reward_url', 'slug', 'country', 'category'], axis=1, inplace=True)

    df.to_csv(output_file, header=True, index=False)


# merge_csv_file(data_folder='data/kickstarter raw data', output_file='data/kickstarter_data.csv')
"""
for _ in range(2):
    tic = time.time()
    add_campaign_info('data/raw_kickstarter_data.csv', 'data/raw_kickstarter_data_updated.csv', max_request=200)
    toc = time.time()
    print('Requests finished at {} in {:.5f}s'.format(datetime.now(),  (toc-tic)/1000))
    time.sleep(5 * 60)
"""
pre_processing_data('data/raw_kickstarter_data_updated.csv', 'data/kickstarter_data.csv')
