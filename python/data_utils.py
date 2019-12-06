import requests
from bs4 import BeautifulSoup
from glob import glob
import pandas as pd
import os
import re
from statistics import mean
from datetime import datetime

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
    else:
        rewards = re.findall(r'About <span>.*?\$.*?([0-9]+)</span>.*?pledge__reward-description.*?<p>(.*?)</p>',
                             page_data, re.DOTALL)
        reward_levels = list(map(lambda x: int(x[0]), rewards))
        reward_descriptions = list(map(lambda x: len(x[1]), rewards))

        try:
            faq = re.findall(r'projectFAQsCount&quot;:([0-9]+),', page_data, re.DOTALL)[0]
        except IndexError:
            faq = re.findall(r'FAQ.*?<span class="count">([0-9]+)</span>', page_data, re.DOTALL)[0]

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


def add_campaign_info(data_file, output_file):
    df = pd.read_csv(data_file)

    project_urls = list(df[df['data_status'] == 0]['project_url'].values)

    campaign_data = {'project_url': [], 'rewards_levels': [], 'rewards_min': [], 'rewards_max': [], 'rewards_mean': [],
                     'has_1dollar_reward': [], 'avg_reward_description': [], 'faq': [], 'is_project_we_love': []}

    for i, project_url in enumerate(project_urls):
        print('PROGRESS......................{:04d}'.format(i))
        print(project_url)
        campaign_data, status = collect_campaign_info(project_url, campaign_data)

        if status == 0:
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

    df['deadline'] = list(map(lambda t: datetime.fromtimestamp(t), df['deadline'].values))
    df['launched_at'] = list(map(lambda t: datetime.fromtimestamp(t), df['launched_at'].values))

    df['duration'] = df['deadline'] - df['launched_at']
    df['duration'] = list(map(lambda x: int(x.days), df['duration'].values))

    df['is_asking_for_help'] = list(map(lambda x: is_asking_for_help(x), df['blurb'].values))
    df['blurb_length'] = list(map(lambda x: len(str(x)), df['blurb'].values))

    df['name_length'] = list(map(lambda x: len(str(x)), df['name'].values))

    df['state'] = list(map(lambda x: STATE_MAPPING[str(x)], df['state'].values))

    df['category_code'] = list(map(lambda x: CATEGORY_MAPPING[str(x)], df['category'].values))

    df['country_code'] = list(map(lambda x: COUNTRY_MAPPING[str(x)], df['country'].values))

    df.drop(['blurb', 'created_at', 'deadline', 'id', 'launched_at', 'name', 'project_url',
             'reward_url', 'slug'], axis=1, inplace=True)

    df.to_csv(output_file, header=True, index=False)


# merge_csv_file(data_folder='data/kickstarter raw data', output_file='data/kickstarter_data.csv')
add_campaign_info('data/raw_kickstarter_data.csv', 'data/kickstarter_data.csv')




"""
file = 'data/raw_kickstarter_data.csv'
output_file = 'data/kickstarter_data.csv'

df = pd.read_csv(file)

campaign_data = {'project_url': [], 'rewards_levels': [], 'rewards_min': [], 'rewards_max': [], 'rewards_mean': [],
                 'has_1dollar_reward': [], 'avg_reward_description': [], 'faq': [], 'is_project_we_love': []}

url = 'https://www.kickstarter.com/projects/freecast/freecast-broadcast-high-quality-video-on-the-fly?ref=category'
campaign_data, s = collect_campaign_info(url, campaign_data)

campaign_df = pd.DataFrame.from_dict(campaign_data)

collected_url = {e: 0 for e in campaign_df['project_url'].values}

updated_projects = [u in collected_url for u in df['project_url'].values]
df.loc[updated_projects, 'data_status'] = 1
df.to_csv(file, header=True, index=False)


df_update = pd.merge(df, campaign_df, on='project_url', how='inner')
df_final = pd.read_csv(output_file)
df_final = pd.concat([df_final, df_update], sort=True)
df_final.drop(['data_status'], axis=1, inplace=True)
df_final.to_csv(output_file, header=True, index=False)





file = 'data/raw_kickstarter_data.csv'
output_file = 'data/kickstarter_data.csv'

df = pd.read_csv(file)
n = len(df)
df['data_status'] = [0 for _ in range(n)]
df.to_csv(file, header=True, index=False)



campaign_data = {'project_url': [], 'rewards_levels': [], 'rewards_min': [], 'rewards_max': [], 'rewards_mean': [],
                 'has_1dollar_reward': [], 'avg_reward_description': [], 'faq': [], 'is_project_we_love': []}


cols = list(df.columns)
print(cols)
for key in campaign_data:
    cols.append(key)


pd.DataFrame(columns=cols).to_csv(output_file, header=True, index=False)




url = 'https://www.kickstarter.com/projects/freecast/freecast-broadcast-high-quality-video-on-the-fly?ref=category'
campaign_data, s = collect_campaign_info(url, campaign_data)

campaign_df = pd.DataFrame.from_dict(campaign_data)

collected_url = {e: 0 for e in campaign_df['project_url'].values}

updated_projects = [u in collected_url for u in df['project_url'].values]
df.loc[updated_projects, 'data_status'] = 1
df.to_csv(file, header=True, index=False)


df_update = pd.merge(df, campaign_df, on='project_url', how='inner')
df_final = pd.read_csv(output_file)
df_final = pd.concat([df_final, df_update], sort=True)
df_final.drop(['data_status'], axis=1, inplace=True)
df_final.to_csv(output_file, header=True, index=False)



page_info = ['project_url', 'rewards_levels', 'rewards_min', 'rewards_max', 'rewards_mean',
             'has_1dollar_reward', 'avg_reward_description', 'faq', 'is_project_we_love']





campaign_data = {'project_url': [], 'rewards_levels': [], 'rewards_min': [], 'rewards_max': [], 'rewards_mean': [],
                 'has_1dollar_reward': [], 'avg_reward_description': [], 'faq': [], 'is_project_we_love': []}

df_status1 = df[df['data_status'] == 1]


url = 'https://www.kickstarter.com/projects/freecast/freecast-broadcast-high-quality-video-on-the-fly?ref=category'
data, s = collect_campaign_info(url, campaign_data)








file = 'data/kickstarter_data.csv'
df = pd.read_csv(file)
n = len(df)
df['data_status'] = [0 for _ in range(n)]

df['rewards_levels'] = [0 for _ in range(n)]
df['rewards_min'] = [0 for _ in range(n)]
df['rewards_max'] = [0 for _ in range(n)]
df['rewards_mean'] = [0 for _ in range(n)]
df['has_1dollar_reward'] = [0 for _ in range(n)]
df['avg_reward_description'] = [0 for _ in range(n)]
df['faq'] = [0 for _ in range(n)]
df['is_project_we_love'] = [0 for _ in range(n)]

df.to_csv(file, header=True, index=False)




for idx in range(2):
    print(idx)
    file = 'data/parts/kickstarter_data_part{}.csv'.format(idx)
    file2 = 'data/rst/kickstarter_data_part{}.csv'.format(idx)
    add_campaign_info(file, file2)
    print()




url = 'https://www.kickstarter.com/projects/artemisprotocol/the-artemis-protocol-a-new-type-of-female-action-m?ref=category'
# url = 'https://www.kickstarter.com/projects/freecast/freecast-broadcast-high-quality-video-on-the-fly?ref=category'
response = requests.get(url)

content = response.text

if re.findall(r'been hidden for privacy.*?This project has been removed from visibility at the request of the creator',
              content, re.DOTALL):
    print('ok')



with open('test3.txt', 'w') as f:
    f.write(content)





idx = 0
file = 'data/parts/kickstarter_data_part{}.csv'.format(idx)
file2 = 'data/rst/kickstarter_data_part{}.csv'.format(idx)
add_campaign_info(file, file2)







idx = 0
file = 'data/parts/kickstarter_data_part{}.csv'.format(idx)
file2 = 'data/rst/kickstarter_data_part{}.csv'.format(idx)
add_campaign_info(file, file2)











df = pd.read_csv('data/kickstarter_data.csv')
n = len(df)
p = 200
k = n // p

for i in range(p):
    print(i)
    df.iloc[i*k:(i+1)*k, :].to_csv('data/parts/kickstarter_data_part{}.csv'.format(i), header=True, index=False)









i = 0
file = 'data/test/kickstarter_data_part{}.csv'.format(i)
df = pd.read_csv(file)
add_campaign_info(file, file)









import requests
url = 'https://www.kickstarter.com/projects/1965847877/tana-hagens-figurehead-project?ref=category'
url = 'https://www.kickstarter.com/projects/598750078/john-and-man-in-suit?ref=discovery_category_newest'

import time


tic = time.time()
response = requests.get(url)

content = response.text

with open('test3.txt', 'w') as f:
  f.write(content)

rewards = re.findall(r'About <span>\$([0-9]+)</span>.*?pledge__reward-description.*?<p>(.*?)</p>', content, re.DOTALL)
reward_levels = list(map(lambda x: int(x[0]), rewards))
reward_descriptions = list(map(lambda x: len(x[1]), rewards))

faq, updates, comments = re.findall(r'FAQsCount&quot;:([0-9]+).*updateCount&quot;:([0-9]+).*comments-count="([0-9]+)"',
                                  content, re.DOTALL)[0]

is_project_we_love = int(bool(re.match(r'.*Project We Love.*', content, re.DOTALL)))






print(reward_levels)
print(reward_descriptions)
print(faq, updates, comments)
print(is_project_we_love)


print(time.time() - tic)
print()

with open('test3.txt', 'w') as f:
  f.write(content)


tic = time.time()
url_get = requests.get(url)
soup = BeautifulSoup(url_get.content, 'html.parser')

page_data = soup.text



reward_levels = list(map(int, re.findall(r'About\s*U?S?\$\s*([0-9]+)', page_data)))

print(reward_levels)
print(time.time() - tic)



project_url = 'https://www.kickstarter.com/projects/598750078/john-and-man-in-suit?ref=discovery_category_newest/'

df,_ = pd.read_html(project_url)
print(df.head())


df = pd.read_csv('data/kickstarter_data.csv')
n = len(df)
p = 20
k = n // p

for i in range(p):
  print(i)
  df.iloc[i*k:(i+1)*k, :].to_csv('data/test/kickstarter_data_part{}.csv'.format(i), header=True, index=False)






def f(x):
  url = re.findall(r'(https?://www.kickstarter.com/projects/.*\?ref=).*', str(x))[0]
  return url + 'category'

d1 = {}
d2 = {}

df = pd.read_csv('data/kickstarter_data2.csv')

for _, row in df.iterrows():

  iden = row['id']

  if iden not in d1:
      d1[iden] = row['project_url']

  if iden not in d2:
      d2[iden] = row['reward_url']

df['project_url'] = list(map(lambda x: d1[x], df['id'].values))
df['reward_url'] = list(map(lambda x: d2[x], df['id'].values))
df.drop_duplicates(inplace=True)
df.to_csv('data/kickstarter_data2.csv', header=True, index=False)
print(len(df))


df = pd.read_csv('data/kickstarter_data2.csv')
n = len(df)
k = n // 10

for i in range(10):
  print(i)
  df.iloc[i*k:(i+1)*k, :].to_csv('data/test/kickstarter_data_part{}.csv'.format(i), header=True, index=False)







project_url = 'https://www.kickstarter.com/projects/598750078/john-and-man-in-suit?ref=discovery_category_newest'
url_get = requests.get(project_url)
soup = BeautifulSoup(url_get.content, 'html.parser')

page_data = soup.text

if re.match(r'.*has been hidden for privacy.*', page_data, re.DOTALL):
  print('ok')
else:
  print('bad')
  
  
  
def collect_campaign_info(project_url, data):
  url_get = requests.get(project_url)
  soup = BeautifulSoup(url_get.content, 'html.parser')

  page_data = soup.text

  if re.match(r'.*has been hidden for privacy.*', page_data, re.DOTALL):
      return data

  reward_levels = list(map(int, re.findall(r'About\s*U?S?\$\s*([0-9]+)', page_data)))

  reward_descriptions = re.findall(r'About.*?[0-9]+(.*?)Less', page_data, re.DOTALL)
  reward_descriptions = list(map(lambda x: len(re.sub(r'[\n|\t|\s]+', ' ', x.strip())), reward_descriptions))

  data['project_url'].append(project_url)
  data['rewards_levels'].append(len(reward_levels))
  data['rewards_min'].append(min(reward_levels))
  data['rewards_max'].append(max(reward_levels))
  data['rewards_mean'].append(int(mean(reward_levels)))
  data['has_1dollar_reward'].append(int(1 in reward_levels))
  data['avg_reward_description'].append(int(mean(reward_descriptions)))

  faq = re.findall(r'FAQ[^a-zA-Z]*?([0-9]+)', page_data, re.DOTALL)
  if not faq:
      data['faq'].append(0)
  else:
      data['faq'].append(int(faq[0]))

  comment = re.findall(r'Comments[^a-zA-Z]*?([0-9]+)', page_data, re.DOTALL)
  if not comment:
      data['comments'].append(0)
  else:
      data['comments'].append(int(comment[0]))

  update = re.findall(r'Updates[^a-zA-Z]*?([0-9]+)', page_data, re.DOTALL)
  if not comment:
      data['updates'].append(0)
  else:
      data['updates'].append(int(update[0]))

  return data

"""