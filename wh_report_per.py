import datetime
import requests
import json
import pandas
from pytz import timezone
import io
import streamlit as st
import pydeck as pdk
import dateutil.parser

st.set_page_config(layout="wide")

CLAIM_SECRETS = st.secrets["CLAIM_SECRETS"]
CLIENT_LIST = st.secrets["CLIENTS"]
#SHEET_KEY = st.secrets["SHEET_KEY"]
#SHEET_ID = st.secrets["SHEET_ID"]
API_URL = st.secrets["API_URL"]
FILE_BUFFER = io.BytesIO()
client_timezone = "America/Lima"

def get_claims(secret, date_from, date_to, cursor=0):
    url = API_URL
    timezone_offset = "-05:00"
    payload = json.dumps({
        "created_from": f"{date_from}T00:00:00{timezone_offset}",
        "created_to": f"{date_to}T23:59:59{timezone_offset}",
        "limit": 1000,
        "cursor": cursor
    }) if cursor == 0 else json.dumps({"cursor": cursor})

    headers = {
        'Content-Type': 'application/json',
        'Accept-Language': 'en',
        'Authorization': f"Bearer {secret}"
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    claims = json.loads(response.text)
    cursor = None
    try:
        cursor = claims['cursor']
        print(f"CURSOR: {cursor}")
    except:
        print("LAST PAGE PROCESSED")
    try:
        return claims['claims'], cursor
    except:
        return [], None

def check_islast (row, df):
    row["islast"] = "True"
    df_temp = df[df["unique"].isin([row["unique"]])]
    last = df_temp["status_time"].max()
    
    #for index, row_df in df.iterrows():
    if row["status_time"] < last:
            row["islast"] = "False"
    return row

def get_report(option="Today", start_=None, end_=None) -> pandas.DataFrame:
    
    offset_back = 0
    if option == "Yesterday":
        offset_back = 1
    elif option == "Tomorrow":
        offset_back = -1
    elif option == "Received":
        offset_back = 0
    
    client_timezone = "America/Lima"

    if option == "Monthly":
        start_ = "2023-06-01"
        end_ = "2023-07-31"
        today = datetime.datetime.now(timezone(client_timezone))
        date_from_offset = datetime.datetime.fromisoformat(start_).astimezone(
            timezone(client_timezone)) - datetime.timedelta(days=1)
        date_from = date_from_offset.strftime("%Y-%m-%d")
        date_to = end_
    elif option == "Two weeks":
        start_date = datetime.datetime.now(timezone(client_timezone))-datetime.timedelta(days=datetime.datetime.weekday(datetime.datetime.now(timezone(client_timezone)))+7)
        end_date=start_date + datetime.timedelta(days=13)
        start_ = start_date.strftime("%Y-%m-%d")
        end_ = end_date.strftime("%Y-%m-%d")
        #start_ = "2023-06-26"
        #end_ = "2023-07-02"
        today = datetime.datetime.now(timezone(client_timezone))
        date_from_offset = datetime.datetime.fromisoformat(start_).astimezone(
            timezone(client_timezone)) - datetime.timedelta(days=1)
        date_from = date_from_offset.strftime("%Y-%m-%d")
        date_to = end_
    elif option == "Received":
        today = datetime.datetime.now(timezone(client_timezone)) - datetime.timedelta(days=offset_back)
        search_from = today.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=7)
        search_to = today.replace(hour=23, minute=59, second=59, microsecond=999999) + datetime.timedelta(days=2)
        date_from = search_from.strftime("%Y-%m-%d")
        date_to = search_to.strftime("%Y-%m-%d")        
    else:
        today = datetime.datetime.now(timezone(client_timezone)) - datetime.timedelta(days=offset_back)
        search_from = today.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=2)
        search_to = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        date_from = search_from.strftime("%Y-%m-%d")
        date_to = search_to.strftime("%Y-%m-%d")

    today = today.strftime("%Y-%m-%d")
    report = []
    i = 0
    for secret in CLAIM_SECRETS:
        claims, cursor = get_claims(secret, date_from, date_to)
        while cursor:
            new_page_claims, cursor = get_claims(secret, date_from, date_to, cursor)
            claims = claims + new_page_claims
        print(f"{datetime.datetime.now()}: Processing {len(claims)} claims")
        for claim in claims:
            try:
                claim_from_time = claim['same_day_data']['delivery_interval']['from']
            except:
                continue
            cutoff_time = datetime.datetime.fromisoformat(claim_from_time).astimezone(timezone(client_timezone))
            cutoff_date = cutoff_time.strftime("%Y-%m-%d")
            if not start_ and option != "Received":
                if cutoff_date != today:
                    continue
            report_cutoff = cutoff_time.strftime("%Y-%m-%d %H:%M")
            try:
                report_client_id = claim['route_points'][0]['external_order_id']
            except:
                report_client_id = "External ID not set"
            try:
                report_barcode = claim['route_points'][1]['external_order_id']
            except:
                report_barcode = "Barcode not set"
            report_claim_id = claim['id']
            try:
                report_lo_code = claim['items'][0]['extra_id']
            except:
                report_lo_code = "No LO code"
            report_client = CLIENT_LIST[i]
            report_pickup_address = claim['route_points'][0]['address']['fullname']
            report_pod_point_id = str(claim['route_points'][1]['id'])
            report_receiver_address = claim['route_points'][1]['address']['fullname']
            report_receiver_phone = claim['route_points'][1]['contact']['phone']
            report_receiver_name = claim['route_points'][1]['contact']['name']
            try:
                report_comment = claim['comment']
            except:
                report_comment = "Missing comment in claim"
            report_status = claim['status']
            report_created_time = dateutil.parser.isoparse(claim['created_ts']).astimezone(timezone(client_timezone))
            report_status_time = datetime.datetime.strptime(claim['updated_ts'],"%Y-%m-%dT%H:%M:%S.%f%z").astimezone(
        timezone(client_timezone))
            report_longitude = claim['route_points'][1]['address']['coordinates'][0]
            report_latitude = claim['route_points'][1]['address']['coordinates'][1]
            report_store_longitude = claim['route_points'][0]['address']['coordinates'][0]
            report_store_latitude = claim['route_points'][0]['address']['coordinates'][1]
            report_corp_id = claim['corp_client_id']
            try:
                report_courier_name = claim['performer_info']['courier_name']
                report_courier_park = claim['performer_info']['legal_name']
            except:
                report_courier_name = "No courier yet"
                report_courier_park = "No courier yet"
            try:
                report_return_reason = str(claim['route_points'][1]['return_reasons'])
#                report_return_comment = claim['route_points'][1]['return_comment']
            except:
                report_return_reason = "No return reasons"
#               report_return_comment = "No return comments"
            try:
                report_route_id = claim['route_id']
            except:
                report_route_id = "No route"
            try:
                report_point_B_time = datetime.datetime.strptime(claim['route_points'][1]['visited_at']['actual'],"%Y-%m-%dT%H:%M:%S.%f%z").astimezone(
        timezone(client_timezone))
                report_point_B_time = report_point_B_time.strftime("%Y-%m-%d %H:%M:%S")
            except:
                report_point_B_time = "Point B was never visited"
            try:
                #st.write(claim['route_points'][2]['visited_at']['actual'])
                report_point_C_time = datetime.datetime.strptime(claim['route_points'][2]['visited_at']['actual'],"%Y-%m-%dT%H:%M:%S.%f%z").astimezone(timezone(client_timezone))
                #report_point_C_time = report_point_C_time.strftime("%Y-%m-%d %H:%M:%S")
            except:
                report_point_C_time = "Point C was never visited"  
            row = [report_cutoff, report_created_time, report_client, report_client_id, report_barcode, report_claim_id, report_lo_code, report_status, report_status_time, 
                   report_pod_point_id, report_pickup_address, report_receiver_address, report_receiver_phone, report_receiver_name, report_comment,
                   report_courier_name, report_courier_park,
                   report_return_reason, report_route_id,
                   report_longitude, report_latitude, report_store_longitude, report_store_latitude, report_corp_id, report_point_B_time, report_point_C_time,"", "", ""]
            report.append(row)
        i = i + 1
    
    print(f"{datetime.datetime.now()}: Building dataframe")
    result_frame = pandas.DataFrame(report,
                                    columns=["cutoff", "created_time", "client", "client_id", "barcode", "claim_id", "lo_code", "status", "status_time",
                                             "pod_point_id", "pickup_address", "receiver_address", "receiver_phone", "receiver_name", "client_comment", 
                                             "courier_name", "courier_park",
                                             "return_reason", "route_id", "lon", "lat", "store_lon", "store_lat",
                                             "corp_client_id", "point_B_time","point_C_time", "filter_date", "unique", "islast"])
#     orders_with_pod = get_pod_orders()
#     result_frame = result_frame.apply(lambda row: check_for_pod(row, orders_with_pod), axis=1)
#    try:
#        result_frame.insert(3, 'proof', result_frame.pop('proof'))
#    except:
#        print("POD failed/ disabled")
    print(f"{datetime.datetime.now()}: Constructed dataframe")
    return result_frame


st.markdown(f"# Peru warehouse routes report")

if st.sidebar.button("Refresh data 🔮", type="primary"):
    st.cache_data.clear()
st.sidebar.caption(f"Page reload doesn't refresh the data.\nInstead, use this button to get a fresh report")

#option = st.sidebar.selectbox(
#    "Select report date:",
#    ["Weekly", "Monthly", "Received", "Today", "Yesterday", "Tomorrow"]  # Disabled Monthly for now
#)

option = "Two weeks"
@st.cache_data(ttl=1800.0)
def get_cached_report(option):
    report = get_report(option)
    return report


df = get_cached_report(option)        
#delivered_today = len(df[df['status'].isin(['delivered', 'delivered_finish'])])
start_date = datetime.datetime.now(timezone(client_timezone))-datetime.timedelta(days=datetime.datetime.weekday(datetime.datetime.now(timezone(client_timezone)))+7)
end_date=start_date + datetime.timedelta(days=13)

filters = st.sidebar.date_input("select returns on which dates you're interested in",value = (datetime.datetime.now(timezone(client_timezone)),datetime.datetime.now(timezone(client_timezone))), min_value = start_date, max_value = end_date)
filter_from = filters[0] 
if len(filters)<2:
    filter_to = filter_from
else:
    filter_to = filters[1]
returning = st.sidebar.checkbox("Include returning orders")
df["unique"] = df["client"]+df["barcode"]
returns_df = df[df['status'].isin(['returning','returned','returned_finish'])]
returns_df = returns_df.apply(lambda row: check_islast(row, df), axis=1)
returns_df = returns_df[returns_df["islast"].isin(["True"])]
def check_date (strangething,filter_from,filter_to):
    if strangething == "Point C was never visited":
        if returning:
            return True
        else:
            return False
    else:
        if strangething.date()>=filter_from and strangething.date()<=filter_to:
            return True
        else:
            return False
returns_df["filter_date"] = returns_df["point_C_time"].apply(lambda a: check_date(a,filter_from,filter_to))
try:
    returns_df = returns_df[returns_df["filter_date"].isin([True])]
except Exception as error:
    st.write(error)
returns_df = returns_df.drop(["islast","unique","filter_date"], axis=1)
st.write(returns_df)


client_timezone = "America/Lima"
TODAY = datetime.datetime.now(timezone(client_timezone)).strftime("%Y-%m-%d") \
    if option == "Today" \
    else datetime.datetime.now(timezone(client_timezone)) - datetime.timedelta(days=1)
returns_df["status_time"] = returns_df["status_time"].apply(lambda a: a.strftime("%Y-%m-%d %H:%M:%S"))
returns_df["point_C_time"] = returns_df["point_C_time"].apply(lambda a: a if a == "Point C was never visited" else a.strftime("%Y-%m-%d %H:%M:%S"))
#returns_df["point_C_time"] = returns_df["point_C_time"].apply(lambda a: a.strftime("%Y-%m-%d %H:%M:%S"))
returns_df["created_time"] = returns_df["created_time"].apply(lambda a: pandas.to_datetime(a).date()).reindex()
with pandas.ExcelWriter(FILE_BUFFER, engine='xlsxwriter') as writer:
    
    returns_df.to_excel(writer, sheet_name='wh_routes_report')
    writer.close()

    st.download_button(
        label="Download report as xlsx",
        data=FILE_BUFFER,
        file_name=f"route_report_{TODAY}.xlsx",
        mime="application/vnd.ms-excel"
    )
