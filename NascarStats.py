import pandas as pd
import json
import requests
import datetime
import streamlit as st
import plotly.graph_objs as go
import plotly.express as px
from PIL import Image
from plotly.subplots import make_subplots 

DRIVER_URL = 'https://cf.nascar.com/cacher/drivers.json'
SCHEDULE_CUP_URL = 'https://cf.nascar.com/cacher/2023/1/race_list_basic.json'
SCHEDULE_NBS_URL = 'https://cf.nascar.com/cacher/2023/2/race_list_basic.json'
SCHEDULE_NCS_URL = 'https://cf.nascar.com/cacher/2023/3/race_list_basic.json'

#Get schedule overview data
#Create function to sort down to past races and only points race

def FilterSchedule(schedule):
    schedule['race_date']= pd.to_datetime(schedule['race_date'])
    schedule = schedule[(schedule.race_date < datetime.datetime.now()) & (schedule.race_type_id == 1)]
    return schedule
 
df_schedule_cup = FilterSchedule(pd.json_normalize(json.loads(requests.get(SCHEDULE_CUP_URL).text)))
df_schedule_nbs = FilterSchedule(pd.json_normalize(json.loads(requests.get(SCHEDULE_NBS_URL).text)))
df_schedule_ncs = FilterSchedule(pd.json_normalize(json.loads(requests.get(SCHEDULE_NCS_URL).text)))

#Combine / merge all tables into 1
df_schedule_master = pd.concat([df_schedule_cup,df_schedule_nbs,df_schedule_ncs]).reset_index(drop=True)

#Get list of all races completed
races = pd.unique(df_schedule_master['race_id'])

#create function to loop races and get the data and compile to 1 df
def CompileRaceData(race,race_id):
    data_race = pd.json_normalize(json.loads(requests.get(f'https://cf.nascar.com/loopstats/prod/2023/{race_id}/{race}.json').text)[0]['drivers'])
    data_race['race_id'] = race
    return data_race

list_of_df = []

for race in races:
    try:
        df_race = CompileRaceData(race, df_schedule_master[df_schedule_master.race_id == race].series_id.item())
        list_of_df.append(df_race)
    except:
        variable = 'error'

df_race_master = pd.concat(list_of_df).reset_index(drop=True)

# Get Driver overview data
data_driver = json.loads(requests.get(DRIVER_URL).text)
df_driver = pd.json_normalize(data_driver['response'])

#add in mfg correct name
df_driver['manf_name']=df_driver['Manufacturer'].map(lambda x: "Chevrolet" if "Chevy" in x else ( "Ford" if "ford" in x else ("Toyota" if "Toyota" in x else "")))

#Join Drivers to race master
df_driver = df_driver.rename({'Nascar_Driver_ID':'driver_id'},axis='columns')
df_master = pd.merge(df_race_master, df_driver, on='driver_id', how='left')

#Join Schedule to race Master
df_master = pd.merge(df_master, df_schedule_master, on='race_id', how='left')

#create winner table to aid with overall win %
df_winner = df_master.loc[(df_master['ps']==1)]

#DF of first finishers of each mfg
mfgs = ['Chevrolet','Ford','Toyota']

#Function to get mfg points
#logic is get first car of mfg and that race
list_of_teamdf = []
list_of_teamcumdf = []

def PointsCalc(row):
    if row['ps'] == 1:
        val = 40
    else:
        val = 36-row['ps']
    return val

def GetOwnersPoints(team,race):
    data_mfg = df_master.loc[(df_master['manf_name'] ==f'{team}') & (df_master['race_id']==race)]
    data_mfg = data_mfg[data_mfg['ps']==data_mfg['ps'].min()]
    data_mfg['mfg_pts'] = df_mfg.apply(PointsCalc,axis=1)
    return data_mfg

for race in races:
    for team in mfgs:
        df_race = GetOwnersPoints(team, race)
        list_of_teamdf.append(df_race)

#owners points table
df_mfg_points = pd.concat(list_of_teamdf).reset_index(drop=True)

#get CumSum of points for chart
def CumSumPoints(team,series):
    df_cs = df_mfg_points[(df_mfg_points['manf_name']==team)&(df_mfg_points['series_id']==series)]
    df_cs['cumsum']=df_cs.mfg_pts.cumsum()
    return df_cs

#Get Win Percentage Total All Series
def GetWinPerc(team,series):
    #Get Count of total races = races list
    total_count = len(df_mfg_points[(df_mfg_points['manf_name']==team)&(df_mfg_points['series_id']==series)])
    total_wins = df_mfg_points[(df_mfg_points['manf_name']==team)&(df_mfg_points['ps']==1)&(df_mfg_points['series_id']==series)].shape[0]
    per_win = total_wins/total_count
    return  per_win*100

def GetTotalWins(team,series):
    return df_mfg_points[(df_mfg_points['manf_name']==team)&(df_mfg_points['ps']==1)&(df_mfg_points['series_id']==series)].shape[0]

def GetTotalPoints(team,series):
    data_races =df_mfg_points[(df_mfg_points['manf_name']==team)&(df_mfg_points['series_id']==series)]
    return data_races['mfg_pts'].sum()

st.set_page_config(layout='wide',page_title='MFG Points',page_icon='https://www.nascar.com/wp-content/uploads/sites/7/fbrfg/favicon-32x32.png')

header = st.container()
model = st.container()
boxdata = st.container()
topdata = st.container()
dataset = st.container()

#order is set at top...
with header:
    st.markdown(""" <style>
        footer {visibility: hidden;}
        </style> """, unsafe_allow_html=True)

    st.markdown("""
        <style>
               .block-container {
                padding-top: 1rem;
                padding-bottom: 0rem;
                padding-left: 5rem;
                padding-right: 5rem;
                }
        </style>
        """, unsafe_allow_html=True)

    st.markdown(
    """
    <h1 style='text-align: center', 'display: inline-block', 'line-height: unset'>
        <img src ="https://www.nascar.com/wp-content/uploads/sites/7/2023/01/75thAnniversary_IDMark_rgb-1-1-5.png" style='float: left', 'vertical-align: middle'>Manufacturer Points Overview
    </h1>
    """,
    unsafe_allow_html=True
    )

with boxdata:
    st.markdown("""<hr style="height:5px;border:none;color:#333;background-color:#333;" /> """, unsafe_allow_html=True)
    seriesoption = st.selectbox('Select Series', ('Cup','Xfinity','Truck','All'))

    st.markdown(
    f"""
    <style>
    text-align:center,
    display:inline-block,
    line-height:unset
    </style>
    <h2> {seriesoption} Series Overview </h2>
    """,
    unsafe_allow_html=True
    )

    b1,b2,b3 = st.columns((1,1,1))

    b1.markdown(
    """
    <h2 style='text-align: center', 'display: inline-block', 'line-height: unset'>
        <img src ="https://www.chevrolet.com/content/dam/chevrolet/na/us/english/primary-navigation-icons/chevrolet-logo-v2.png" style='align:middle', 'vertical-align: middle'>
    </h2>
    """,
    unsafe_allow_html=True
    )

    b2.markdown(
    """
    <h2 style='text-align: center', 'display: inline-block', 'line-height: unset'>
        <img src ="https://performance.ford.com/apps/settings/wcm/designs/fordracing/clientlibs_layout/resources/img/logo_fordracing-footer-dark.png" style='align:middle;height:87px;', 'vertical-align: middle'>
    </h2>
    """,
    unsafe_allow_html=True
    )

    b3.markdown(
    """
    <h2 style='text-align: center', 'display: inline-block', 'line-height: unset'>
        <img src ="https://www.toyota.com/content/dam/brandguidelines/layout/logo.svg" style='height:87px;align:middle', 'vertical-align: middle'>
    </h2>
    """,
    unsafe_allow_html=True
    )

    st.markdown('''
        <style>
        /*center metric label*/
        [data-testid="stMetricLabel"] > div:nth-child(1) {
            justify-content: center;
        }

        /*center metric value*/
        [data-testid="stMetricValue"] > div:nth-child(1) {
            justify-content: center;
        }

        /*center metric value*/
        [data-testid="stMetricValue"] > div:nth-child(1) {
            justify-content: center;
        }
        </style>
        ''', unsafe_allow_html=True)

    def getOptionNo (option):
        if option == 'Cup' :
            return 1
        if option == 'Xfinity':
             return 2
        if option == 'Truck': 
            return 3
        return 0

    b1.metric("Wins",GetTotalWins("Chevrolet",getOptionNo(seriesoption)))
    b2.metric("Wins", GetTotalWins("Ford",getOptionNo(seriesoption)))
    b3.metric("Wins",GetTotalWins("Toyota",getOptionNo(seriesoption)))


    #group by and sum
    b1.metric("Points",GetTotalPoints("Chevrolet",getOptionNo(seriesoption)))
    b2.metric("Points", GetTotalPoints("Ford",getOptionNo(seriesoption)))
    b3.metric("Points",GetTotalPoints("Toyota",getOptionNo(seriesoption)))

    c1,c2,c3 = st.columns((1,1,1))

    layout = go.Layout(margin=go.layout.Margin(
        l=0,
        r=0,
        b=0,
        t=0,
    ))

    fig1 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=GetWinPerc("Chevrolet",getOptionNo(seriesoption)),
        gauge={'shape':'angular',
               'axis' : {'range':[None,100]},
               }
    ))

    fig2 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=GetWinPerc("Ford",getOptionNo(seriesoption)),
        gauge={'shape':'angular',
               'axis' : {'range':[None,100]},
                },
        title={'text':"Win Percentage"}
    ))

    fig3 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=GetWinPerc("Toyota",getOptionNo(seriesoption)),
        gauge={'shape':'angular',
               'axis' : {'range':[None,100]},
               }
    ))

    c1.plotly_chart(fig1,use_container_width=True,layout=layout)
    c2.plotly_chart(fig2,use_container_width=True,layout=layout)
    c3.plotly_chart(fig3,use_container_width=True,layout=layout)

    with dataset:
        
        #Overview of finish position vs track
        st.subheader('Total Points by Team')
        fig = px.bar(df_mfg_points.loc[(df_mfg_points['series_id']==getOptionNo(seriesoption))],y='mfg_pts',x='manf_name',color = 'Team', barmode = 'stack', text_auto=True,
            labels={'mfg_pts':'Manufactuer Points', 'manf_name':''})
        st.plotly_chart(fig,use_container_width=True)

        for team in mfgs:
            list_of_teamcumdf.append(CumSumPoints(team,getOptionNo(seriesoption)))

        df_cumsum = pd.concat(list_of_teamcumdf).reset_index(drop=True)

        st.subheader('Total Points by Track')
        fig = px.line(df_cumsum.loc[(df_cumsum['series_id']==getOptionNo(seriesoption))],y='cumsum',x='race_name',color = 'manf_name',labels={'cumsum':'Manufactuer Points', 'race_name':'','manf_name':'Manufacturer'},
            color_discrete_map={
                 "Chevrolet": "#d2a74c",
                 "Ford": "#1b376a",
                 "Toyota":"#eb0b1f"})
        st.plotly_chart(fig,use_container_width=True)

        st.subheader('Overview Manufacturer Finish Position')
        fig4 = px.box(df_master.loc[(df_master['series_id']==getOptionNo(seriesoption))],x='ps',y='race_name',color='manf_name',points="all",labels={'ps':'Finish Position', 'race_name':'','manf_name':'Manufacturer'},
        color_discrete_map={
                 "Chevrolet": "#d2a74c",
                 "Ford": "#1b376a",
                 "Toyota":"#eb0b1f"})
        st.plotly_chart(fig4,use_container_width=True)
