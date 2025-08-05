import streamlit as st
import pandas as pd
import altair as alt
import json

# --- Load Data ---
@st.cache_data
def load_data():
    df = pd.read_csv("Sampled_Incident_Reports.csv", low_memory=False)
    df["Incident Datetime"] = pd.to_datetime(df["Incident Datetime"], errors="coerce", utc=True)
    df = df.dropna(subset=["Incident Datetime", "Latitude", "Longitude"])
    df["date"] = df["Incident Datetime"].dt.floor("D")
    df["hour"] = df["Incident Datetime"].dt.hour
    df["year"] = df["Incident Datetime"].dt.year
    df["weekday"] = df["Incident Datetime"].dt.day_name()
    df["month"] = df["Incident Datetime"].dt.month
    df["day"] = df["Incident Datetime"].dt.day
    df["Analysis Neighborhood"] = df["Analysis Neighborhood"].fillna("Unknown")
    return df

def norm_res(r):
    resolved_keys = ["ARREST", "BOOKED", "CITED", "CLEARED", "EXCEPTIONAL"]
    r_up = str(r).upper()
    return "Resolved" if any(k in r_up for k in resolved_keys) else "Open"

def limit_data(df, max_rows=5000):
    if len(df) > max_rows:
        return df.sample(max_rows, random_state=42)
    return df

# Load Data and GeoJSON
df = load_data()
df['resolution_status'] = df['Resolution'].apply(norm_res)
df['Incident Category'] = df['Incident Category'].fillna('Unknown').astype(str)

with open('sf_neighborhoods.geojson', 'r') as f:
    sf_geo = json.load(f)

st.title("San Francisco Crime Dashboard")
tab2, tab1, tab3, tab4, tab5, about_tab, creators_tab = st.tabs(["Map", "Time Series", "Day of Week", "Category+Resolution", "Neighborhood Comparison", "About", "Creators"])

with tab1:
    st.subheader("Incidents Over Time by Category")
    st.info("The line chart shows how the volume of each incident type changes through time in different neighborhoods.\n\n**Instruction:** Select the incident category and neighborhood in the dropdown.")
    category_options = ['All'] + sorted(df['Incident Category'].unique())
    col1, col2 = st.columns([1,1])
    with col1:
        selected_category = st.selectbox("Select Incident Category", category_options)
    with col2:
        selected_neighborhood_ts = st.selectbox("Select Neighborhood", ['All'] + sorted(df['Analysis Neighborhood'].unique()), key='neigh_select_tab1')

    df_filtered = df
    if selected_category != 'All':
        df_filtered = df_filtered[df_filtered['Incident Category'] == selected_category]
    if selected_neighborhood_ts != 'All':
        df_filtered = df_filtered[df_filtered['Analysis Neighborhood'] == selected_neighborhood_ts]

    df_time_series = df_filtered.groupby([pd.Grouper(key='date', freq='M'), 'Incident Category']).size().reset_index(name='count')

    chart = (
        alt.Chart(df_time_series)
        .mark_line(point=True)
        .encode(
            x=alt.X('date:T', title='Month'),
            y=alt.Y('count:Q', title='Incident Count'),
            color=alt.Color('Incident Category:N'),
            tooltip=[alt.Tooltip('date:T', title='Month'), alt.Tooltip('Incident Category:N'), alt.Tooltip('count:Q', title='Count')]
        )
        .properties(width=800, height=400)
    )

    st.altair_chart(chart, use_container_width=True)

with tab2:
    st.subheader("Incident Bubble Map")
    st.info("Each bubble represents one count of incident. Discover how crime moves across the city through time.\n\n**Instruction:** Select the year, month, and day of your desired view. Adjust the hour slider to see each incident.")
    selected_year_heatmap = st.selectbox("Select Year", sorted(df['year'].unique()), index=sorted(df['year'].unique()).index(2025), key='year_select_heatmap')
    month_options = ['All'] + sorted(df['month'].unique())
    selected_month = st.selectbox("Select Month", month_options, key='month_select_heatmap')
    day_options = ['All'] + sorted(df['day'].unique())
    selected_day = st.selectbox("Select Day", day_options, key='day_select_heatmap')
    selected_hour = st.slider("Select Hour", 0, 23, 12, key='hour_select_heatmap')

    df_heatmap = df[df['year'] == selected_year_heatmap]
    if selected_month != 'All':
        df_heatmap = df_heatmap[df_heatmap['month'] == selected_month]
    if selected_day != 'All':
        df_heatmap = df_heatmap[df_heatmap['day'] == selected_day]
    df_heatmap = df_heatmap[df_heatmap['hour'] == selected_hour]

    neighborhood_options = ['All'] + sorted(df_heatmap['Analysis Neighborhood'].unique())
    selected_neighborhood = st.selectbox("Select Neighborhood", neighborhood_options, key='heatmap_neighborhood_drilldown')

    if selected_neighborhood != 'All':
        df_heatmap_filtered = df_heatmap[df_heatmap['Analysis Neighborhood'] == selected_neighborhood]
    else:
        df_heatmap_filtered = df_heatmap

    base_map = alt.Chart(alt.Data(values=sf_geo['features'])).mark_geoshape(
        fill='lightgrey', stroke='white', strokeWidth=1.5
    ).encode(
        tooltip=[alt.Tooltip('properties.name:N', title='Neighborhood')]
    ).project('mercator').properties(width=700, height=500)

    heatmap = alt.Chart(df_heatmap_filtered).mark_circle().encode(
        longitude='Longitude:Q',
        latitude='Latitude:Q',
        size=alt.Size('count()', scale=alt.Scale(range=[0, 1000])),
        color=alt.Color('count()', scale=alt.Scale(scheme='redyellowblue'), legend=None),
        tooltip=[
            alt.Tooltip('Incident Category:N', title='Category'),
            alt.Tooltip('Analysis Neighborhood:N', title='Neighborhood'),
            alt.Tooltip('month(date):N', title='Month'),
            alt.Tooltip('day(date):N', title='Day'),
            alt.Tooltip('hour:Q', title='Hour'),
            alt.Tooltip('count()', title='Incident Count')
        ]
    ).properties(width=700, height=500)

    st.altair_chart(base_map + heatmap)

    df_neigh = df_heatmap_filtered

    st.subheader(f"Category Breakdown in {selected_neighborhood}")
    cat_counts = df_neigh['Incident Category'].value_counts().reset_index()
    cat_counts.columns = ['Incident Category', 'count']
    bar = alt.Chart(cat_counts).mark_bar().encode(
        y=alt.Y('Incident Category:N', sort='-x'),
        x='count:Q'
    ).properties(width=700, height=300)
    st.altair_chart(bar)

    st.subheader(f"Monthly Trends in {selected_neighborhood}")
    time_series = df_neigh.groupby(pd.Grouper(key='date', freq='M')).size().reset_index(name='count')
    line = alt.Chart(time_series).mark_line(point=True).encode(
        x='date:T', y='count:Q'
    ).properties(width=700, height=300)
    st.altair_chart(line)

with tab3:
    st.info("The bar chart shows how the volume of incidents changes through the week at different hours across police districts.\n\n**Instruction:** Select the police district and adjust the hour of the day with the slider.")
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_hour = st.slider("Hour of Day", 0, 23, 12, key='hour_slider_tab5')
        selected_district = st.selectbox("Police District", sorted(df['Police District'].dropna().unique()), key='district_select_tab3')
    with col2:
        st.subheader(f"Incidents by Day of Week — Hour: {selected_hour}, District: {selected_district}")
        df_day = df[(df['hour'] == selected_hour) & (df['Police District'] == selected_district)]
        df_day_agg = df_day['weekday'].value_counts().reset_index()
        df_day_agg.columns = ['weekday', 'count']
        day_chart = alt.Chart(df_day_agg).mark_bar().encode(
            x=alt.X('weekday:N', sort=['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']),
            y='count:Q'
        ).properties(width=600, height=300)
        st.altair_chart(day_chart)

with tab4:
    st.subheader("Category and Resolution Overview")
    st.info("This section explores the distribution of incident categories and how resolutions vary across police districts.\n\n**Instruction:** Select a year and optionally filter by incident category to see the breakdown of cases and their resolution status across different districts.")
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_year = st.selectbox("Select Year", sorted(df['year'].unique()), key='year_select_tab4')
        incident_category_filter = st.selectbox("Filter by Incident Category", ['All'] + sorted(df['Incident Category'].unique()), key='incident_cat_filter_tab4')
    with col2:
        df_cat = df[df['year'] == selected_year]
        if incident_category_filter != 'All':
            df_cat = df_cat[df_cat['Incident Category'] == incident_category_filter]

        st.subheader(f"Incident Categories in {selected_year}")
        cat_counts = df_cat['Incident Category'].value_counts().reset_index()
        cat_counts.columns = ['Incident Category', 'count']
        cat_chart = alt.Chart(cat_counts).mark_bar().encode(
            y=alt.Y('Incident Category:N', sort='-x'),
            x='count:Q'
        )
        st.altair_chart(cat_chart)

        st.subheader("Resolution Status by District")
        pie_base = alt.Chart(df_cat).mark_arc().encode(
            theta='count()',
            color=alt.Color('resolution_status:N'),
            tooltip=['resolution_status:N', 'count()']
        ).properties(width=120, height=120)

        pie_facet = pie_base.facet(column='Police District:N')
        st.altair_chart(pie_facet)

with about_tab:
    st.header("About")
    st.markdown("""
    This dashboard provides an interactive exploration of San Francisco Police Incident Reports, enabling users to examine crime trends across neighborhoods, time periods, and incident categories.

    Designed for data-driven storytelling, it combines heatmaps, time series trends, category breakdowns, and resolution rates to uncover spatial and temporal crime patterns.

    **Data Source:** [San Francisco Police Department Incident Reports](https://data.sfgov.org/Public-Safety/Police-Department-Incident-Reports-2018-to-Present/wg3w-h783/about_data)
    """)

with creators_tab:
    st.header("Creators")
    st.markdown("""
    **Zia Williams**  
    **Brandon Zhou**  
    Developed as part of a visualization project to explore public safety data with accessible and actionable insights.
    """)

with tab5:
    st.subheader("Neighborhood Comparison")
    st.info("The bar charts show the distribution of incident categories in different neighborhoods, allowing direct comparison.\n\n**Instruction:** Select two neighborhoods in the dropdown to compare.")
    col1, col2 = st.columns([1, 1])
    with col1:
        neigh1 = st.selectbox("Neighborhood 1", sorted(df['Analysis Neighborhood'].unique()), key='neigh1_select_tab5')
    with col2:
        neigh2 = st.selectbox("Neighborhood 2", sorted(df['Analysis Neighborhood'].unique()), key='neigh2_select_tab5')

    df_neigh1 = df[df['Analysis Neighborhood'] == neigh1]
    df_neigh2 = df[df['Analysis Neighborhood'] == neigh2]

    bar1 = alt.Chart(df_neigh1).mark_bar().encode(
        y=alt.Y('Incident Category:N', sort='-x'),
        x='count()',
        color='Incident Category:N'
    ).properties(width=300, height=500, title=f'Incidents — {neigh1}')

    bar2 = alt.Chart(df_neigh2).mark_bar().encode(
        y=alt.Y('Incident Category:N', sort='-x'),
        x='count()',
        color='Incident Category:N'
    ).properties(width=300, height=500, title=f'Incidents — {neigh2}')

    st.altair_chart(bar1 | bar2)

