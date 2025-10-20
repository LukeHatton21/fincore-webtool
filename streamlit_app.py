import streamlit as st
import folium
import altair as alt
import pandas as pd
import numpy as np
from streamlit_folium import st_folium
import branca.colormap as cm
from wacc_prediction_v2 import WaccPredictor
from visualiser import VisualiserClass
import altair as alt
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.lines as mlines
from matplotlib.legend_handler import HandlerTuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# Call WaccPredictor Object
wacc_predictor = WaccPredictor(crp_data = "./DATA/CRPs.csv", 
generation_data="./DATA/Ember Yearly Data 2023.csv", GDP="./DATA/GDPPerCapita.csv",
tax_data="./DATA/CORPORATE_TAX_DATA.csv", ember_targets="./DATA/Ember_2030_Targets.csv", 
us_ir="./DATA/US_IR.csv", imf_data="./DATA/IMF_Projections.csv", collated_crp_cds="./DATA/Collated_CRP_CDS.xlsx")

# Call visualiser
visualiser = VisualiserClass(wacc_predictor.crp_data, wacc_predictor.calculator.tech_premiums)
country_names = sorted(visualiser.crp_dictionary.keys())
tech_names = sorted(visualiser.tech_dictionary.keys())
tech_names = [x for x in tech_names if x !="Other"]


# Create title
st.title("Financing Costs for Renewables Estimator (FinCoRE)")
col1, col2 = st.columns(2)

# Take inputs of year, technology and country
with col1:
        year = st.selectbox(
                "Year", ("2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028", "2029", "2030"), 
                index=9, key="Year", placeholder="Select Year...")
with col2:
        technology = st.selectbox(
                "Displayed Technology", tech_names, 
                index=7, placeholder="Select Technology...", key="Technology")
        technology = visualiser.tech_dictionary.get(technology)
country_selection = st.selectbox(
        "Country", options=country_names, 
        index=3, placeholder="Select Country of Interest...", key="CountryProjections")
country_selection = visualiser.crp_dictionary.get(country_selection)

# Set out input tabs and calculate the share of cost of capital
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["💸 Blended Finance", "📊 WACC", "🌐 Map", "🥇Comparison", "🔭Projections", "🛠️Technologies", "📝 About"])
yearly_waccs = wacc_predictor.calculate_historical_waccs(year, technology)
with tab1:
    st.title("Ratio of Blended Finance")
    st.write(f"Finance for energy projects can come from a range of sources, including both domestic and international financiers. It can also be directed through commercial or public sources, with some role for grant funding in certain markets. Set the blended finance ratios for {technology} in {year} here.")
    concessionality = st.selectbox(
        "Select Financing Terms for International Public Finance...(%)", ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Commercial Rate"), index=5, key="IPF", placeholder="Select financing terms for international public finance...(%)")
    shares_df = visualiser.vertical_sliders()
with tab2:
    st.title("Weighted Cost of Capital")
    df, overall_cost = wacc_predictor.calculate_weighted_average(shares_df=shares_df, year=year, technology=technology, 
                                                  country_code=country_selection, concessionality=concessionality)
    #df = pd.DataFrame(data={"source": ["International Commercial", "International Public", "Domestic Commercial", "Domestic Public", "Grant"], "Share": [25, 25, 20, 25, 5], "Cost of Capital": [10, 7, 8, 9, 0.1]})
    visualiser.show_source_average(df, overall=overall_cost)
with tab3:
    st.title("Cost of Capital from International Commercial Investors")
    visualiser.display_map(yearly_waccs, technology)
with tab4:
    st.header("Global Estimates")
    selected_countries = st.multiselect("Countries to compare", options=yearly_waccs['Country code'].values, default=["USA", "IND", "GBR", "JPN", "CHN", "BRA"])
    sorted_waccs = visualiser.sort_waccs(yearly_waccs)
    visualiser.plot_ranking_table(sorted_waccs, selected_countries)

with tab5: 
    st.header("Historical and Projected Estimates")
    
    options = ["Interest Rate Change", "Renewable Growth", "GDP Change"]
    options_mapping = {"Interest Rate Change": "interest_rate", "Renewable Growth": "renewable_targets", "GDP Change": "gdp_change"}
    if country_selection is not None:
        projection_assumptions = st.pills("Projection Assumptions", options, selection_mode="multi")
        for i in projection_assumptions:
            name = options_mapping.get(i)
            globals()[f"{name}"] = f"{name}"
        if "Interest Rate Change" not in projection_assumptions:
            interest_rate = None
        if "Renewable Growth" not in projection_assumptions:
            renewable_targets = None
        if "GDP Change" not in projection_assumptions:
            gdp_change = None
        historical_country_data = wacc_predictor.year_range_wacc(start_year=2015, end_year=2023, 
                                                             technology=technology, country=country_selection)
        if len(projection_assumptions) > 0:
            future_waccs = wacc_predictor.projections_wacc(end_year=2029, technology=technology, country=country_selection, 
                                                    interest_rates=interest_rate, GDP_change=gdp_change, renewable_targets=renewable_targets)
            historical_country_data = pd.concat([future_waccs, historical_country_data])
        historical_country_data = historical_country_data.drop(columns = ["Debt_Share", "Equity_Cost", "Debt_Cost", "Tax_Rate", "Country code", "WACC"])
        visualiser.plot_comparison_chart(historical_country_data)
    
with tab6: 
    st.header("Technology Comparison")
    country_tech_selection = st.selectbox(
        "Country", options=country_names, 
         index=None, placeholder="Select Country of Interest...", key="CountryTechs")
    selected_techs = st.multiselect("Technologies to compare", options=tech_names, default=["Solar PV", "Hydroelectric", "Gas Power (CCGT)"])
    print(tech_names)
    selected_techs = [visualiser.tech_dictionary.get(x) for x in selected_techs]
    country_tech_selection = visualiser.crp_dictionary.get(country_tech_selection)
    
    if country_tech_selection is not None:
        country_technology_comparison = wacc_predictor.calculate_technology_wacc(year=year, country=country_tech_selection, technologies=selected_techs)
        sorted_tech_comparison = visualiser.sort_waccs(country_technology_comparison)
        visualiser.plot_ranking_table_tech(sorted_tech_comparison, selected_techs)
with tab7: 
    text = open('about.md').read()
    st.write(text)
    