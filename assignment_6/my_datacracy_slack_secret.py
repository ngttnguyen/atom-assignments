
# Ref: https://towardsdatascience.com/data-apps-with-pythons-streamlit-b14aaca7d083

#/app.py
import streamlit as st
import json
import requests
# import sys
# import os
import pandas as pd
import numpy as np
import re
from datetime import datetime as dt
from pandas_profiling import ProfileReport
from streamlit_pandas_profiling import st_profile_report
from matplotlib import pyplot as plt
import seaborn as sns

# Initial setup
# st.set_page_config(layout="wide")
# with open('./env_variable.json','r') as j:
#     json_data = json.load(j)

#SLACK_BEARER_TOKEN = os.environ.get('SLACK_BEARER_TOKEN') ## Get in setting of Streamlit Share
# SLACK_BEARER_TOKEN = json_data['SLACK_BEARER_TOKEN']

SLACK_BEARER_TOKEN = st.secrets["SLACK_BEARER_TOKEN"] # lấy từ secrete của streamlit

DTC_GROUPS_URL = ('https://raw.githubusercontent.com/anhdanggit/atom-assignments/main/data/datacracy_groups.csv')
#st.write(json_data['SLACK_BEARER_TOKEN'])

@st.cache
def load_users_df():
    # Slack API User Data
    endpoint = "https://slack.com/api/users.list"
    headers = {"Authorization": "Bearer {}".format(SLACK_BEARER_TOKEN)}
    response_json = requests.post(endpoint, headers=headers).json() 
    user_dat = response_json['members']

    # Convert to CSV
    user_dict = {'user_id':[],'name':[],'display_name':[],'real_name':[],'title':[],'is_bot':[]}
    for i in range(len(user_dat)):
        user_dict['user_id'].append(user_dat[i]['id'])
        user_dict['name'].append(user_dat[i]['name'])
        user_dict['display_name'].append(user_dat[i]['profile']['display_name'])
        user_dict['real_name'].append(user_dat[i]['profile']['real_name_normalized'])
        user_dict['title'].append(user_dat[i]['profile']['title'])
        user_dict['is_bot'].append(int(user_dat[i]['is_bot']))
    user_df = pd.DataFrame(user_dict) 
    # Read dtc_group hosted in github
    dtc_groups = pd.read_csv(DTC_GROUPS_URL)
    user_df = user_df.merge(dtc_groups, how='left', on='name')
    return user_df

@st.cache
def load_channel_df():
    endpoint2 = "https://slack.com/api/conversations.list"
    data = {'types': 'public_channel,private_channel'} # -> CHECK: API Docs https://api.slack.com/methods/conversations.list/test
    headers = {"Authorization": "Bearer {}".format(SLACK_BEARER_TOKEN)}
    response_json = requests.post(endpoint2, headers=headers, data=data).json() 
    channel_dat = response_json['channels']
    channel_dict = {'channel_id':[], 'channel_name':[], 'is_channel':[],'creator':[],'created_at':[],'topics':[],'purpose':[],'num_members':[]}
    for i in range(len(channel_dat)):
        channel_dict['channel_id'].append(channel_dat[i]['id'])
        channel_dict['channel_name'].append(channel_dat[i]['name'])
        channel_dict['is_channel'].append(channel_dat[i]['is_channel'])
        channel_dict['creator'].append(channel_dat[i]['creator'])
        channel_dict['created_at'].append(dt.fromtimestamp(float(channel_dat[i]['created'])))
        channel_dict['topics'].append(channel_dat[i]['topic']['value'])
        channel_dict['purpose'].append(channel_dat[i]['purpose']['value'])
        channel_dict['num_members'].append(channel_dat[i]['num_members'])
    channel_df = pd.DataFrame(channel_dict) 
    return channel_df

@st.cache(allow_output_mutation=True)
def load_msg_dict(user_df,channel_df):
    endpoint3 = "https://slack.com/api/conversations.history"
    headers = {"Authorization": "Bearer {}".format(SLACK_BEARER_TOKEN)}
    msg_dict = {'channel_id':[],'msg_id':[], 'msg_ts':[], 'user_id':[], 'latest_reply':[],'reply_user_count':[],'reply_users':[],'github_link':[],'text':[]}
    for channel_id, channel_name in zip(channel_df['channel_id'], channel_df['channel_name']):
        print('Channel ID: {} - Channel Name: {}'.format(channel_id, channel_name))
        try:
            data = {"channel": channel_id} 
            response_json = requests.post(endpoint3, data=data, headers=headers).json()
            msg_ls = response_json['messages']
            for i in range(len(msg_ls)):
                if 'client_msg_id' in msg_ls[i].keys():
                    msg_dict['channel_id'].append(channel_id)
                    msg_dict['msg_id'].append(msg_ls[i]['client_msg_id'])
                    msg_dict['msg_ts'].append(dt.fromtimestamp(float(msg_ls[i]['ts'])))
                    msg_dict['latest_reply'].append(dt.fromtimestamp(float(msg_ls[i]['latest_reply'] if 'latest_reply' in msg_ls[i].keys() else 0))) ## -> No reply: 1970-01-01
                    msg_dict['user_id'].append(msg_ls[i]['user'])
                    msg_dict['reply_user_count'].append(msg_ls[i]['reply_users_count'] if 'reply_users_count' in msg_ls[i].keys() else 0)
                    msg_dict['reply_users'].append(msg_ls[i]['reply_users'] if 'reply_users' in msg_ls[i].keys() else 0) 
                    msg_dict['text'].append(msg_ls[i]['text'] if 'text' in msg_ls[i].keys() else 0) 
                    ## -> Censor message contains tokens
                    text = msg_ls[i]['text']
                    github_link = re.findall('(?:https?://)?(?:www[.])?github[.]com/[\w-]+/?', text)
                    msg_dict['github_link'].append(github_link[0] if len(github_link) > 0 else None)
        except:
            print('====> '+ str(response_json))
    msg_df = pd.DataFrame(msg_dict)
    return msg_df

def process_msg_data(msg_df, user_df, channel_df):
    ## Extract 2 reply_users
    msg_df['reply_user1'] = msg_df['reply_users'].apply(lambda x: x[0] if x != 0 else '')
    msg_df['reply_user2'] = msg_df['reply_users'].apply(lambda x: x[1] if x != 0 and len(x) > 1 else '')
    ## Merge to have a nice name displayed
    msg_df = msg_df.merge(user_df[['user_id','name','DataCracy_role']].rename(columns={'name':'submit_name'}), \
        how='left',on='user_id')
    msg_df = msg_df.merge(user_df[['user_id','name']].rename(columns={'name':'reply1_name','user_id':'reply1_id'}), \
        how='left', left_on='reply_user1', right_on='reply1_id')
    msg_df = msg_df.merge(user_df[['user_id','name']].rename(columns={'name':'reply2_name','user_id':'reply2_id'}), \
        how='left', left_on='reply_user2', right_on='reply2_id')
    ## Merge for nice channel name
    msg_df = msg_df.merge(channel_df[['channel_id','channel_name','created_at']], how='left',on='channel_id')
    ## Format datetime cols
    msg_df['created_at'] = msg_df['created_at'].dt.strftime('%Y-%m-%d')
    msg_df['msg_date'] = msg_df['msg_ts'].dt.strftime('%Y-%m-%d')
    msg_df['msg_time'] = msg_df['msg_ts'].dt.strftime('%H:%M')
    msg_df['msg_weekday'] = msg_df['msg_ts'].dt.strftime('%w')
    msg_df['msg_hour'] = msg_df['msg_ts'].dt.strftime('%H')
    msg_df['wordcount'] = msg_df.text.apply(lambda s: len(s.split()))
    return msg_df

def get_submission(p_msg_df, user_id):
    '''Return 'channel_name', 'created_at','msg_date','msg_time','reply_user_count', 'reply1_name' of 
        submission
    '''
    ## Submission
    submit_df = p_msg_df[p_msg_df.channel_name.str.contains('assignment')]
    submit_df = submit_df[submit_df.DataCracy_role.str.contains('Learner')]
    submit_df = submit_df[submit_df.user_id == user_id]
    latest_ts = submit_df.groupby(['channel_name', 'user_id']).msg_ts.idxmax() ## -> Latest ts
    submit_df = submit_df.loc[latest_ts]
    dis_cols1 = ['channel_name', 'created_at','msg_date','msg_weekday','msg_time','msg_hour','reply_user_count', 'reply1_name']
    return(submit_df[dis_cols1])

def get_review(p_msg_df, user_id):
    ''''Return channel_name', 'created_at','msg_date','msg_time','reply_user_count','submit_name'
        review
    '''
    # Review
    review_df = p_msg_df[p_msg_df.user_id != user_id] ##-> Remove the case self-reply
    review_df = p_msg_df[p_msg_df.channel_name.str.contains('assignment')]
    review_df = review_df[review_df.DataCracy_role.str.contains('Learner')]

    dis_cols2 = ['channel_name', 'created_at','msg_date','msg_time','reply_user_count','submit_name']
    return(review_df [dis_cols2])

def get_discussion(p_msg_df):
    '''''Return channel_name','msg_date', 'msg_time','wordcount','reply_user_count','reply1_name' of
        discussion
    '''
    ## Discussion
    discuss_df = p_msg_df[p_msg_df.channel_name.str.contains('discuss')]
    discuss_df = discuss_df.sort_values(['msg_date','msg_time'])
    dis_cols3 = ['channel_name','msg_date', 'msg_time','wordcount','reply_user_count','reply1_name']
    return(discuss_df[dis_cols3])

def get_report(p_msg_df, user_id):
    '''''Return 'user_id', 'submit_name', 'DataCracy_role', 'submit_cnt', 'review_cnt', 'reviewed_rate', 'word_count', 
            'submit_weekday', 'submit_hour' of given user_id
         report_cols = ['user_id', 'submit_name', 'DataCracy_role', 'submit_cnt', 'review_cnt', 'reviewed_rate', 'word_count', 
            'submit_weekday', 'submit_hour']
    '''
    
    ### chỉ lấy những message liên quan user_id theo mức user_id là người tạo, hoặc là replier1/ repliers
    filter_msg_df = p_msg_df[(p_msg_df.user_id == user_id) | (p_msg_df.reply_user1 == user_id) | (p_msg_df.reply_user2 == user_id)]

    submit_df = get_submission(filter_msg_df, user_id)
    review_df = get_review(filter_msg_df, user_id)
    discuss_df = get_discussion(filter_msg_df)

    ## Thổng kê data
    ### Số assignment đã nộp: submit_cnt
    ### % bài review        : review_cnt
    ### % bài được review   : reviewed_rate
    ### Số workcount đã thảo luận: word_count
    ### Extract thứ trong tuần (weekday) của ngày nộp bài: submit_weekday
    ### Extract giờ trong ngày nộp bài (hour): submit_hour

    filter_report_df = filter_msg_df[filter_msg_df['user_id'] ==  user_id].head(1)[['user_id','submit_name', 'DataCracy_role']]

    submit_cnt = len(submit_df)
    review_cnt = len(review_df)
    reviewed_rate = round(100 * len(submit_df[submit_df.reply_user_count > 0])/submit_cnt if submit_cnt > 0  else 0, 2)
    word_count = round(sum(discuss_df['wordcount']),2)
    submit_weekday =round(submit_df['msg_weekday'].astype('int32').mean(),2)
    submit_hour = round(submit_df['msg_hour'].astype('int32').mean(),2)

    filter_report_df['submit_cnt'] = submit_cnt 
    filter_report_df['review_cnt'] = review_cnt
    filter_report_df['reviewed_rate'] = reviewed_rate
    filter_report_df['word_count'] = word_count
    filter_report_df['submit_weekday'] = submit_weekday
    filter_report_df['submit_hour'] = submit_hour
    
    return (filter_report_df)
    
def get_Atom_report(msg_df, user_df, channel_df):
    # Table data
    # user_df = load_users_df()
    # channel_df = load_channel_df()
    # msg_df = load_msg_dict(user_df,channel_df)
    
    # processing data
    p_msg_df = process_msg_data(msg_df, user_df, channel_df)
    
    report_df = pd.DataFrame()

    for user_id in p_msg_df[p_msg_df['DataCracy_role'].str.contains('Learner') & p_msg_df['channel_name'].str.contains('assignment')]['user_id'].unique():
        
        filter_report_df = get_report(p_msg_df, user_id)
        report_df = report_df.append(filter_report_df, ignore_index=True)
    
    return (report_df)

    
# def get_df(file):
#   # get extension and read file
#   extension = file.name.split('.')[1]
#   if extension.upper() == 'CSV':
#     df = pd.read_csv(file)
#   elif extension.upper() == 'XLSX':
#     df = pd.read_excel(file, engine='openpyxl')
#   elif extension.upper() == 'PICKLE':
#     df = pd.read_pickle(file)
#   return df


# Function to explore the data
def summary(df, nrows = 5):

  # DATA
  #st.write('Data:')
  #st.write(df.head(nrows))
  # SUMMARY
  df_types = pd.DataFrame(df.dtypes, columns=['Data Type'])
  numerical_cols = df_types[~df_types['Data Type'].isin(['object',
                   'bool'])].index.values
  df_types['Count'] = df.count()
  df_types['Unique Values'] = df.nunique()
  df_types['Min'] = df[numerical_cols].min()
  df_types['Max'] = df[numerical_cols].max()
  df_types['Average'] = df[numerical_cols].mean()
  df_types['Median'] = df[numerical_cols].median()
  df_types['q25'] = df[numerical_cols].quantile(0.25)
  df_types['q75'] = df[numerical_cols].quantile(0.75)
  df_types['q90'] = df[numerical_cols].quantile(0.90)
  #st.write('Summary:')
  st.write(df_types)
    
user_df = load_users_df()
channel_df = load_channel_df()
msg_df = load_msg_dict(user_df,channel_df)
##Get full report
report_df = get_Atom_report(msg_df, user_df, channel_df)

def display_learner_report(user_id):
    #st.markdown('## The report of learner')
    df = report_df[report_df.user_id == user_id]
    st.write(df)
    
def display_top_learner_report(report_data, nrows = 5):

    st.markdown('Top 5 learners ordered by number of submissions and review count:')
    st.write(report_df.sort_values(['submit_cnt','review_cnt'],ascending=False).head(nrows))
    
def setting_sns():
    sns.set(style='white')                                                                                                                                                                                                                                                                            
    
def histo_numerical(report_data,fig_title, fig_label):
    
    fig = plt.figure(figsize=(2,2))
    sns.distplot(a = report_data, label = fig_label, kde = False)
    plt.title(fig_title)
    #plt.xticks(np.arange(0, 2500, step = 200))  # Set label locations.      
    plt.legend()
    st.pyplot(fig)


def main():
    st.title('DataCracy Slack report') 
    
    # Summary report
    # is_display_summary = st.sidebar.checkbox("Display summary of report", value = True)
    is_display_summary = st.checkbox("Display summary of report", value = True)
    if is_display_summary:
        summary(report_df)
    
    # Learner Report
    st.markdown('## View Report Detail')
    learner_option = user_df[user_df.DataCracy_role.str.contains('Learner').fillna(False) & (user_df.is_bot == False)]['user_id'].values
    learner_option = np.append('top_5',learner_option)
    option_id = st.selectbox('Select option:',options = learner_option, index = 0,
                                   format_func = (lambda x: user_df[user_df.user_id == x]['real_name'].values[0] 
                                                  if len(user_df[user_df.user_id == x]['real_name'])>0 else ' Top 5 learners'))
    if option_id == learner_option[0]:
        display_top_learner_report(report_df, nrows = 5)
    else:
        display_learner_report(option_id)
        
    # Histogram
    numerical = [ 'submit_cnt', 'review_cnt', 'reviewed_rate', 'word_count', 
            'submit_weekday', 'submit_hour'] 
    categorical = ['user_id', 'submit_name', 'DataCracy_role']
    
    st.markdown('## Distribution of numerical variables:')
    histo_cols = st.multiselect('Columns', numerical, numerical)
       
    setting_sns()
    row = len(histo_cols)
    fig, ax = plt.subplots(2, 3, figsize=(20, 12))
    for i, subplot in zip(histo_cols, ax.flatten()):
        
        sns.distplot(a = report_df[i], label = i, kde = False, ax = subplot)

    st.pyplot(fig)
    
    # Histogram of weekday:
    weekdays = ("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")
    x = [i for i in range(0,7)]

    fig = plt.figure(figsize = (5,2))
    sns.distplot(a = report_df['submit_weekday'], label="submit_weekday", kde = False)
    plt.title("Histogram for submit_weekday")
    plt.xticks(x, weekdays,rotation=45)
    plt.legend()
    st.pyplot(fig)
    
    # Discussion in groups
    word_counts = report_df.groupby('DataCracy_role')['word_count'].mean()
    fig = plt.figure(figsize=(5,2))
    plt.title("Average number of discuss word count between learner groups")
    sns.barplot(x=word_counts.index, y=word_counts.values )
    st.pyplot(fig)
    
        
    
main()

## Run: streamlit run streamlit/data_glimpse.py