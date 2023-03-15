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
    df_race = CompileRaceData(race, df_schedule_master[df_schedule_master.race_id == race].series_id.item())
    list_of_df.append(df_race)

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

def GetOwnersPoints(team,race):
    data_mfg = df_master.loc[(df_master['manf_name'] ==f'{team}') & (df_master['race_id']==race)]
    data_mfg = data_mfg[data_mfg['ps']==data_mfg['ps'].min()]
    data_mfg['mfg_pts']= 41 - data_mfg['ps']  #1=40,2=39,3=38...   41-ps
    return data_mfg

for race in races:
    for team in mfgs:
        df_team = GetOwnersPoints(team, race)
        list_of_teamdf.append(df_team)

#owners points table
df_mfg_points = pd.concat(list_of_teamdf).reset_index(drop=True)

#Get Win Percentage Total All Series
def GetWinPerc(team):
    #Get Count of total races = races list
    total_count = len(races)
    total_wins = df_mfg_points[(df_mfg_points['manf_name']==team)&(df_mfg_points['ps']==1)].shape[0]
    per_win = total_wins/total_count
    return  per_win*100

def GetTotalWins(team):
    return df_mfg_points[(df_mfg_points['manf_name']==team)&(df_mfg_points['ps']==1)].shape[0]

st.set_page_config(layout='wide')

header = st.container()
model = st.container()
boxdata = st.container()
topdata = st.container()
dataset = st.container()

#order is set at top...
with header:
    st.title("Nascar Manufacturer Points Overview")
    # st.image(image)

with boxdata:
    st.header("Manufacturer Total Wins [All Series]")
    b1,b2,b3 = st.columns((1,1,1))

    b1.metric("Chevrolet",GetTotalWins("Chevrolet"))
    b2.metric("Ford", GetTotalWins("Ford"))
    b3.metric("Toyota",GetTotalWins("Toyota"))

    st.subheader("Percent Total Wins")
    c1,c2,c3 = st.columns((1,1,1))

    layout = go.Layout(margin=go.layout.Margin(
        l=0,
        r=0,
        b=0,
        t=0,
    ))

    fig1 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=GetWinPerc("Chevrolet"),
        gauge={'shape':'angular',
               'axis' : {'range':[None,100]},
               },
        title={'text':"Chevrolet"}
    ))

    fig2 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=GetWinPerc("Ford"),
        gauge={'shape':'angular',
               'axis' : {'range':[None,100]},
               },
        title={'text':"Ford"}
    ))

    fig3 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=GetWinPerc("Toyota"),
        gauge={'shape':'angular',
               'axis' : {'range':[None,100]},
               },
        title={'text':"Toyota"}
    ))

    c1.plotly_chart(fig1,use_container_width=True,layout=layout)
    c2.plotly_chart(fig2,use_container_width=True,layout=layout)
    c3.plotly_chart(fig3,use_container_width=True,layout=layout)

    with dataset:
        st.header("Cup Series Overview")

        #Overview of finish position vs track
        st.subheader('Total Points by Team')
        fig = px.bar(df_mfg_points.loc[(df_mfg_points['series_id']==1)],y='mfg_pts',x='manf_name',color = 'Team', barmode = 'stack')
        st.plotly_chart(fig,use_container_width=True)

        st.subheader('Total Points by Track')
        fig = px.line(df_mfg_points.loc[(df_mfg_points['series_id']==1)],y='mfg_pts',x='race_name',color = 'manf_name')
        st.plotly_chart(fig,use_container_width=True)

        st.subheader('Overview Manufacturer Finish Position')
        fig4 = px.box(df_master.loc[(df_master['series_id']==1)],y='ps',x='race_name',color='manf_name')
        st.plotly_chart(fig4,use_container_width=True)

        
