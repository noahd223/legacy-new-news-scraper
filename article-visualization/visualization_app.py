import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import datetime
import os
from dotenv import load_dotenv

# load environment variables
load_dotenv()

# streamlit config
st.set_page_config(page_title="News Visualizer", layout="wide")
st.title("News Articles Visualization Dashboard")
st.markdown("This dashboard visualizes articles from ABC News, CBS News, The Tab, and BuzzFeed. Use the filters to explore different sources and date ranges.")
st.markdown("""
**Developed by the Data Visualization team at the Digital Engagement Lab**  
**Directed by:** Noah Der Garabedian  
**Contributors:** Justin Lee, Sivani Dronamraju, Sean Gunshenan  
""")

# load data from postgresql
@st.cache_data(ttl=600)  # refresh every 10 minutes instead of 5
def load_data():
    # get database credentials from environment variables
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    # create database connection string
    connection_string = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    engine = create_engine(connection_string)
    
    # optimized query - only select needed columns and add basic filtering
    query = """
    SELECT 
        *
    FROM articles 
    WHERE headline_text IS NOT NULL 
    AND publication_date IS NOT NULL
    AND headline_word_count > 0 
    AND article_word_count > 0
    ORDER BY publication_date DESC
    """
    
    df = pd.read_sql_query(query, engine)
    
    # map the actual column names to standard format
    column_mapping = {
        'source_name': 'source',
        'article_url': 'url',
        'article_section': 'section',
        'publication_date': 'pub_date',
        'headline_text': 'headline',
        'headline_word_count': 'headline_len',
        'article_word_count': 'word_count',
        'num_internal_links': 'internal_links',
        'num_external_links': 'external_links',
        'num_internal_links_within_body': 'num_internal_links_within_body',
        'num_external_links_within_body': 'num_external_links_within_body',
        'scrape_date': 'scrape_date'
    }
    
    # rename columns to match expected format
    df.rename(columns=column_mapping, inplace=True)
    
    # the source names are already in the correct format, no mapping needed
    # just ensure they're properly set
    df['source'] = df['source'].fillna('Unknown')
    
    # clean and standardize data - much faster now with pre-filtered data
    df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce")
    df = df.dropna(subset=["pub_date"])
    
    # ensure numeric columns are properly typed
    numeric_columns = ['headline_len', 'word_count', 'internal_links', 'external_links']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # calculate total links
    df['num_links'] = df['internal_links'].fillna(0) + df['external_links'].fillna(0)
    
    return df

df = load_data()

# data is already filtered in the query, no need for additional filtering

# sidebar filters
st.sidebar.header("🔎 Filters")

sources = st.sidebar.multiselect(
    "Select News Sources",
    options=df["source"].unique(),
    default=df["source"].unique()
)

# set default dates in the sidebar
default_start_date = datetime.date(2024, 1, 1)
default_end_date = df["pub_date"].max().date() if not df.empty else datetime.date.today()

date_min, date_max = df["pub_date"].min(), df["pub_date"].max()
date_range = st.sidebar.date_input(
    "Select Date Range",
    value=[default_start_date, default_end_date],
    min_value=date_min.date() if not df.empty else datetime.date(2020, 1, 1),
    max_value=date_max.date() if not df.empty else datetime.date.today()
)

# filter by headline keywords (comma-separated list)
headline_keywords = st.sidebar.text_input(
    "Headline keywords (comma-separated)",
    key="headline_keywords"
)

# note: article text filtering removed for performance
# if needed, can be added back with a separate query

# filtered data
filtered = df[
    (df["source"].isin(sources)) &
    (df["pub_date"] >= pd.to_datetime(date_range[0])) &
    (df["pub_date"] <= pd.to_datetime(date_range[1]))
]

# apply headline keyword filter
if headline_keywords:
    keywords = [kw.strip() for kw in headline_keywords.split(",") if kw.strip()]
    if keywords:
        filtered = filtered[
            filtered["headline"].str.contains("|".join(keywords), case=False, na=False)
        ]

# note: article text filtering removed since we don't load article_full_text anymore
# to improve performance. if needed, can be added back with a separate query

# 📅 articles Over Time (Bar Chart, Daily, Side-by-Side)
st.subheader("📅 Articles Over Time (Bar Chart, Daily)")
articles_over_time_daily = (
    filtered.groupby([pd.Grouper(key="pub_date", freq="D"), "source"]).size().reset_index(name="count")
)
fig_time_bar_daily = px.bar(
    articles_over_time_daily,
    x="pub_date",
    y="count",
    color="source",
    barmode="group",
    title="Articles Published Over Time (Daily, Side-by-Side)",
    labels={"pub_date": "Publication Date", "count": "Number of Articles", "source": "News Source"}
)
st.plotly_chart(fig_time_bar_daily, use_container_width=True)

st.subheader("✍️ Headline Length Box Plot")
fig_headline = px.box(
    filtered,
    x="source",
    y="headline_len",
    points="all",
    title="Headline Length per Article",
    labels={"headline_len": "Headline Length", "source": "News Source"}
)
st.plotly_chart(fig_headline, use_container_width=True)

# New Visualization for Links
st.subheader("🔗 Internal vs. External Links Analysis")
st.markdown("Use the checkboxes to compare different link types across articles.")

# Checkboxes for toggling link types
col1, col2, col3, col4 = st.columns(4)
show_internal_full = col1.checkbox("Internal Links (Full Article)", value=True)
show_external_full = col2.checkbox("External Links (Full Article)", value=True)
show_internal_body = col3.checkbox("Internal Links (Within Body)", value=True)
show_external_body = col4.checkbox("External Links (Within Body)", value=True)

# create a melted dataframe for the plot based on user selection
plot_data_links = []
print(filtered.columns)
if show_internal_full:
    plot_data_links.append(pd.DataFrame({'source': filtered['source'], 'value': filtered['internal_links'], 'link_type': 'Internal (Full)'}))
if show_external_full:
    plot_data_links.append(pd.DataFrame({'source': filtered['source'], 'value': filtered['external_links'], 'link_type': 'External (Full)'}))
if show_internal_body:
    plot_data_links.append(pd.DataFrame({'source': filtered['source'], 'value': filtered['num_internal_links_within_body'], 'link_type': 'Internal (Body)'}))
if show_external_body:
    plot_data_links.append(pd.DataFrame({'source': filtered['source'], 'value': filtered['num_external_links_within_body'], 'link_type': 'External (Body)'}))

if plot_data_links:
    links_df = pd.concat(plot_data_links)
    fig_links = px.box(
        links_df,
        x="source",
        y="value",
        color="link_type",
        points="all",
        title="Distribution of Links per Article by Source",
        labels={"value": "Number of Links", "source": "News Source", "link_type": "Link Type"}
    )
    st.plotly_chart(fig_links, use_container_width=True)
else:
    st.info("Please select at least one link type to visualize.")

st.subheader("📝 Word Count Box Plot")
fig_word = px.box(
    filtered,
    x="source",
    y="word_count",
    points="all",
    title="Word Count per Article",
    labels={"word_count": "Word Count", "source": "News Source"}
)
st.plotly_chart(fig_word, use_container_width=True)

st.subheader("🔗 Number of Links per Article by Source")
fig_links = px.box(
    filtered,
    x="source",
    y="num_links",
    points="all",
    title="Distribution of Links per Article by News Source",
    labels={"num_links": "Number of Links", "source": "News Source"}
)
st.plotly_chart(fig_links, use_container_width=True)

# 📚 section Popularity Over Time (Line Chart, Daily)
st.subheader("📚 Section Popularity Over Time (Line Chart, Daily)")
section_over_time_daily = (
    filtered.groupby([pd.Grouper(key="pub_date", freq="D"), "section"]).size().reset_index(name="count")
)
fig_section_line_daily = px.line(
    section_over_time_daily,
    x="pub_date",
    y="count",
    color="section",
    title="Section Popularity Over Time (Daily)",
    labels={"pub_date": "Publication Date", "count": "Number of Articles", "section": "Section"}
)
# make the lines thicker
fig_section_line_daily.update_traces(line=dict(width=3))
st.plotly_chart(fig_section_line_daily, use_container_width=True)

# 🧮 average Article Length by Section (Side-by-Side by News Site)
st.subheader("🧮 Average Article Length by Section (by News Site)")
avg_lengths_all = (
    filtered.groupby(["source", "section"])["word_count"]
    .mean()
    .reset_index()
)
fig_avg_length_grouped = px.bar(
    avg_lengths_all,
    x="section",
    y="word_count",
    color="source",
    barmode="group",
    title="Average Word Count per Section (Grouped by News Site)",
    labels={"word_count": "Average Word Count", "section": "Section", "source": "News Site"},
)
st.plotly_chart(fig_avg_length_grouped, use_container_width=True)

# visualization: number of articles by day of the week, separated by source
st.subheader("📅 Articles by Day of the Week (by Source)")

# add a toggle button for relative/absolute bar chart
show_relative = st.checkbox("Click Here to Show as Percentage (Relative Bar Chart)", value=False)

filtered = filtered.copy()  
filtered["weekday"] = filtered["pub_date"].dt.day_name()

if show_relative:
    # calculate percentage of articles for each source by weekday (relative to total for that source)
    weekday_counts = filtered.groupby(["source", "weekday"]).size().reset_index(name="count")
    source_totals = weekday_counts.groupby("source")["count"].transform("sum")
    weekday_counts["percent"] = 100 * weekday_counts["count"] / source_totals
    fig_weekday_source = px.bar(
        weekday_counts,
        x="weekday",
        y="percent",
        color="source",
        category_orders={"weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]},
        title="Percentage of Articles by Day of the Week (by Source, Relative to Source Total)",
        labels={"weekday": "Day of Week", "percent": "Percentage of Articles", "source": "News Source"},
        barmode="group"
    )
else:
    fig_weekday_source = px.histogram(
        filtered,
        x="weekday",
        color="source",
        category_orders={"weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]},
        title="Number of Articles by Day of the Week (by Source, Count of articles)",
        labels={"weekday": "Day of Week", "count": "Number of Articles"},
        barmode="group"
    )

st.plotly_chart(fig_weekday_source, use_container_width=True)

# footer
st.markdown("---")
st.markdown("Data sourced from ABC News, CBS News, The Tab, and BuzzFeed.") 