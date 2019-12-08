import requests
import random
from glob import glob
import pandas as pd
import os
import re
from statistics import mean
import datetime
import time
from tqdm import tqdm
import argparse

# Features used for the merge_csv_file function
FEATURES_TO_EXTRACT = ['blurb', 'category', 'country', 'created_at', 'deadline', 'id', 'launched_at', 'name',
                       'slug', 'state', 'usd_pledged', 'static_usd_rate', 'goal', 'urls', 'creator']
FEATURES = ['blurb', 'category', 'country', 'created_at', 'deadline', 'id', 'launched_at', 'name',
            'slug', 'state', 'usd_pledged', 'usd_goal', 'project_url', 'reward_url', 'creator_id']

# Mapping for the categories for the pre_processing_data function
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

# Mapping for the state for the pre_processing_data function
STATE_MAPPING = {'failed': 0, 'successful': 1}

# Mapping for the countries for the pre_processing_data function
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


def merge_csv_file(data_folder, output_file, remove_duplicates_every=50):
    """
    Merge the csv file from the Web Robots website.
    https://webrobots.io/kickstarter-datasets/

    :param data_folder: folder with all the downloaded files
    :param output_file: csv output file
    :param remove_duplicates_every: frequency to which remove the duplicates from the current output file
    """

    # Collect csv files
    csv_files = glob(data_folder + '/*/Kickstarter*csv', recursive=False)

    # Create output csv file
    df = pd.DataFrame(columns=FEATURES)
    df = df.reindex(sorted(df.columns), axis=1)
    df.to_csv(output_file, index=False, header=True, sep=',')

    # Create temporary file to update the output file
    temp_file = '_temp.'.join(output_file.split('.'))

    for i in tqdm(range(len(csv_files))):

        # Extract and pre process raw data from web robots
        temp_df = pd.read_csv(csv_files[i])[FEATURES_TO_EXTRACT]

        temp_df = temp_df[(temp_df['state'] == 'successful') | (temp_df['state'] == 'failed')]

        temp_df['reward_url'] = temp_df['urls'].apply(lambda e: eval(str(e))['web']['rewards'])

        temp_df['project_url'] = temp_df['urls'].apply(lambda e: eval(str(e))['web']['project'])

        temp_df['usd_goal'] = temp_df['static_usd_rate'] * temp_df['goal']

        temp_df['category'] = temp_df['category'].apply(lambda e: re.findall(
            r'https?://www.kickstarter.com/.*categories/([^/"}]*).*$', str(e))[0].title())
        temp_df['category'] = temp_df['category'].apply(lambda e: re.sub(r'%20', ' ', str(e)))

        temp_df['creator_id'] = temp_df['creator'].apply(lambda e: re.findall(r'id.*?([0-9]+)', str(e))[0])

        temp_df.drop(['static_usd_rate', 'goal', 'creator', 'urls'], axis=1, inplace=True)

        temp_df.drop_duplicates(inplace=True)
        temp_df = temp_df.reindex(sorted(temp_df.columns), axis=1)
        temp_df.to_csv(temp_file, index=False, header=False, sep=',')

        # Update output file
        with open(temp_file, 'r') as f:
            text = f.read()
        with open(output_file, 'a') as f:
            f.write(text)

        # Remove duplicates from current output file to limit its size
        if i % remove_duplicates_every == 0:
            df = pd.read_csv(output_file)
            df.drop_duplicates(inplace=True)
            df.to_csv(output_file, header=True, index=False)

    # Delete temporary file
    os.remove(temp_file)

    # Format final output file
    df = pd.read_csv(output_file)
    df.drop_duplicates(inplace=True)
    df['has_campaign_data'] = 0
    df.to_csv(output_file, header=True, index=False)


def remove_project_duplicates(input_file, output_file):
    """
    Remove projects duplicates by keeping one example for each project.

    :param input_file: input file
    :param output_file: output file
    """

    df = pd.read_csv(input_file)
    df.drop_duplicates(inplace=True)

    data = {column: [] for column in df.columns}
    projects = {}

    for i in tqdm(range(len(df.index))):

        if df.loc[df.index[i], 'id'] not in projects:
            projects[df.loc[df.index[i], 'id']] = True
            for column in df.columns:
                data[column].append(df.loc[df.index[i], column])

    pd.DataFrame.from_dict(data).to_csv(output_file, header=True, index=False)


def add_creator_historic(input_file, output_file):
    """
    Add co variates about the creator of a project.

    :param input_file: input file
    :param output_file: output file
    """

    df = pd.read_csv(input_file)

    creator_campaign_creations = {}
    for i in tqdm(range(len(df.index))):
        creator_id = df.loc[df.index[i], 'creator_id']
        if creator_id not in creator_campaign_creations:
            creator_campaign_creations[creator_id] = []
        creator_campaign_creations[creator_id].append(df.loc[df.index[i], 'created_at'])

    creator_project_no = []
    for i in tqdm(range(len(df.index))):
        creator_id = df.loc[df.index[i], 'creator_id']
        created_at = df.loc[df.index[i], 'created_at']

        nb_older_projects = 1
        for project_timestamp in creator_campaign_creations[creator_id]:
            if project_timestamp < created_at:
                nb_older_projects += 1

        creator_project_no.append(nb_older_projects)

    df['creator_project_no'] = creator_project_no
    df['is_first_project_from_creator'] = df['creator_project_no'].apply(lambda e: int(e == 1))

    df.to_csv(output_file, header=True, index=False)


def collect_campaign_info(url, data):
    """
    Collect campaign info from kickstarter with project url.

    :param url: Kickstarter project url
    :param data: current data collection with all the results
    :return: the update data collection and the weather or not the collection was successful
    """

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
        data['has_one_dollar_reward'].append(int(1 in reward_levels))
        data['avg_reward_description'].append(int(mean(reward_descriptions)))

        data['faq'].append(int(faq))

        data['is_project_we_love'].append(int(bool(re.match(r'.*Project We Love.*', page_data, re.DOTALL))))

        return data, 1


def add_campaign_info(input_file, output_file, max_request=250):
    """
    Update a batch of requests with the campaign info.
    
    :param input_file: input file
    :param output_file: output file
    :param max_request: the maximum number of requests
    """

    df = pd.read_csv(input_file)

    project_urls = list(df[df['has_campaign_data'] == 0]['project_url'].values)
    random.shuffle(project_urls)

    campaign_data = {'project_url': [], 'rewards_levels': [], 'rewards_min': [], 'rewards_max': [], 'rewards_mean': [],
                     'has_one_dollar_reward': [], 'avg_reward_description': [], 'faq': [], 'is_project_we_love': []}

    for i, project_url in enumerate(project_urls):
        print('PROGRESS......................{:03d} / {:03d}'.format(i + 1, max_request))
        print(project_url)
        campaign_data, status = collect_campaign_info(
            project_url, campaign_data)
        time.sleep(0.2)

        if status == 0:
            break

        if i >= max_request - 1:
            break

    campaign_df = pd.DataFrame.from_dict(campaign_data)

    collected_url = {e: 0 for e in campaign_df['project_url'].values}
    updated_projects = [u in collected_url for u in df['project_url'].values]

    df.loc[updated_projects, 'has_campaign_data'] = 1
    df.to_csv(input_file, header=True, index=False)

    df_update = pd.merge(df, campaign_df, on='project_url', how='inner')
    df_final = pd.read_csv(output_file)
    df_final = pd.concat([df_final, df_update], sort=True)
    df_final.drop(['has_campaign_data'], axis=1, inplace=True)
    df_final.to_csv(output_file, header=True, index=False)

    print('DONE')


def batch_collect_campaign_info(input_file, output_file, batch=2, wait=250, max_request=200):
    """
    Update a multiple batches of requests with the campaign info.

    :param input_file: input file
    :param output_file: output file
    :param batch: batch size
    :param wait: the seconds to wait between each request
    :param max_request: max number of request by batch for collect mode
    """

    for k in range(batch):
        tic = time.time()
        add_campaign_info(input_file=input_file, output_file=output_file, max_request=max_request)
        toc = time.time()
        print('Batch {} / {} finished at {} in {:d}m{:d}s'.format(k + 1, batch,
                                                                  datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                                                                  int((toc - tic)) // 60,
                                                                  int((toc - tic)) % 60))
        if k < batch - 1:
            time.sleep(wait)


def is_asking_for_help(blurb):
    """
    Function to detect if a blurb is asking for help from teh backers.
    :param blurb: the blurb
    :return: if a blurb is asking for help from the backers
    """

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


def pre_processing_data(input_file, output_file):
    """
    Pre process Kickstarter data.

    :param input_file: input file
    :param output_file: output file
    """

    df = pd.read_csv(input_file)
    time_origin = datetime.datetime(1970, 1, 1)
    df['deadline'] = df['deadline'].apply(lambda t: int((datetime.datetime.fromtimestamp(t) - time_origin).days))
    df['launched_at'] = df['launched_at'].apply(lambda t: int((datetime.datetime.fromtimestamp(t) - time_origin).days))

    df['duration'] = df['deadline'] - df['launched_at']

    df['is_asking_for_help'] = df['blurb'].apply(lambda x: is_asking_for_help(x))
    df['blurb_length'] = df['blurb'].apply(lambda x: len(str(x)))
    df['blurb_word_count'] = df['blurb'].apply(lambda x: len(str(x).split(' ')))

    df['name_length'] = list(map(lambda x: len(str(x)), df['name'].values))
    df['name_word_count'] = df['name'].apply(lambda x: len(str(x).split(' ')))

    df['state'] = df['state'].apply(lambda x: STATE_MAPPING[str(x)])

    for category in CATEGORY_MAPPING:
        col_name = 'category_{}'.format(category.lower())
        col_name = re.sub(r'[^a-zA-Z]', ' ', col_name.strip())
        col_name = re.sub(r'\s+', '_', col_name)
        df[col_name] = df['category'].apply(lambda x: int(x == category))

    df['has_faq'] = df['faq'].apply(lambda x: int(x > 0))

    for country in COUNTRY_MAPPING:
        col_name = 'country_{}'.format(country.lower())
        df[col_name] = df['country'].apply(lambda x: int(x == country))

    df.drop(['blurb', 'created_at', 'deadline', 'id', 'launched_at', 'name', 'project_url',
             'reward_url', 'slug', 'country', 'category', 'creator_id'], axis=1, inplace=True)

    df = df.reindex(sorted(df.columns), axis=1)
    df.to_csv(output_file, header=True, index=False)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Data pipeline to extract and pre process Kickstarter data.')

    parser.add_argument('--mode', '-m', type=str, default='collect', required=True,
                        choices=['merge', 'collect', 'features', 'sandbox'],
                        help='Action to perform.')

    parser.add_argument('--data_folder', '-d', type=str, default=None, required=False,
                        help='Folder with all the files from the Web Robots website.')

    parser.add_argument('--input_file', '-i', type=str, default=None, required=False,
                        help='Input csv file.')

    parser.add_argument('--output_file', '-o', type=str, default=None, required=False,
                        help='Output csv file.')

    parser.add_argument('--batch', '-b', type=int, default=2, required=False,
                        help='Batch size for collect mode.')

    parser.add_argument('--wait', '-w', type=int, default=250, required=False,
                        help='Duration to wait between requests for collect mode.')

    parser.add_argument('--max_request', '-max_r', type=int, default=200, required=False,
                        help='Max number of request by batch for collect mode.')

    parser.add_argument('--remove_duplicates_every', '-r', type=int, default=50, required=False,
                        help='Frequency to which remove the duplicates from the current output file.')

    args = parser.parse_args()

    if args.mode == 'merge':
        # Example:
        # python3 kickstarter_main.py --mode merge

        if args.data_folder is None:
            args.data_folder = '../data/web_robots'

        if args.output_file is None:
            args.output_file = '../data/raw_kickstarter_data.csv'

        """
        print('Merge File')
        merge_csv_file(data_folder=args.data_folder,
                       output_file=args.output_file,
                       remove_duplicates_every=args.remove_duplicates_every)

        print('Remove Duplicates')
        remove_project_duplicates(input_file=args.output_file,
                                  output_file=args.output_file)
        """
        print('Add Creator Historic')
        add_creator_historic(input_file=args.output_file,
                             output_file=args.output_file)

    elif args.mode == 'collect':
        # Example:
        # python3 kickstarter_main.py --mode collect --batch 5 --wait 250 --max_request 200

        if args.input_file is None:
            args.input_file = '../data/raw_kickstarter_data.csv'

        if args.output_file is None:
            args.output_file = '../data/raw_kickstarter_data_with_campaign_info.csv'

        batch_collect_campaign_info(input_file=args.input_file,
                                    output_file=args.output_file,
                                    batch=args.batch,
                                    wait=args.wait,
                                    max_request=args.max_request)

    elif args.mode == 'features':
        # Example:
        # python3 kickstarter_main.py --mode features

        if args.input_file is None:
            args.input_file = '../data/raw_kickstarter_data_with_campaign_info.csv'

        if args.output_file is None:
            args.output_file = '../data/kickstarter_data.csv'

        pre_processing_data(input_file=args.input_file,
                            output_file=args.output_file)

    else:
        # Example:
        # python3 kickstarter_main.py --mode sandbox

        pass
