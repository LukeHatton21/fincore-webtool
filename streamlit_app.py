import streamlit as st
import folium
import altair as alt
import pandas as pd
import numpy as np
from streamlit_folium import st_folium
import branca.colormap as cm
from wacc_estimator import WaccEstimator
from visualiser import VisualiserClass
import altair as alt
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.lines as mlines
from matplotlib.legend_handler import HandlerTuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots

@st.cache_data
def convert_for_download(df):
    return df.to_csv().encode("utf-8")

# Call WaccPredictor Object
wacc_estimator = WaccEstimator(crp_data = "./DATA/CRPs.csv", 
generation_data="./DATA/Ember Yearly Data 2026.csv", GDP="./DATA/GDPPerCapita.csv",
tax_data="./DATA/CORPORATE_TAX_DATA.csv", ember_targets="./DATA/Ember_2030_Targets.csv", 
us_ir="./DATA/US_IR.csv", imf_data="./DATA/IMF_Projections.csv", collated_crp_cds="./DATA/Collated_CRP_CDS.xlsx")

# Call visualiser
visualiser = VisualiserClass(wacc_estimator.crp_data, wacc_estimator.calculator.tech_premiums)
country_names = sorted(visualiser.crp_dictionary.keys())
tech_names = sorted(visualiser.tech_dictionary.keys())
tech_names = [x for x in tech_names if x !="Other"]
all_codes = [visualiser.crp_dictionary.get(x) for x in country_names]
all_techs = [visualiser.tech_dictionary.get(x) for x in tech_names]

shares_df = visualiser.financing_inputs_sidebar()

# Create title
st.title("Financing Costs for Renewables Estimator (FinCoRE)")
col1, col2 = st.columns(2)

# Take inputs of year, technology and country
with col1:
        year = st.selectbox(
                "Year", ("2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028", "2029", "2030", "2031", "2032", "2033", "2034", "2035"), 
                index=9, key="Year", placeholder="Select Year...")
        country_select = st.selectbox(
        "Country", options=country_names, 
        index=2, placeholder="Select Country of Interest...", key="CountryProjections")
        country_selection = visualiser.crp_dictionary.get(country_select)
        merchant_risk = st.checkbox("Exposure to Merchant Risk", key="MerchantRisk")
with col2:
        technology = st.selectbox(
                "Displayed Technology", tech_names, 
                index=7, placeholder="Select Technology...", key="Technology")
        technology = visualiser.tech_dictionary.get(technology)
        concessionality = st.selectbox(
    "Select Level of Concessionality..(%)", ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Commercial Rate"), index=5, key="IPF", placeholder="Select financing terms for international public finance...(%)")
        currency_risk = st.checkbox("Exposure to Currency Risk", key="CurrencyRisk")


# Set out input tabs and calculate the share of cost of capital
tab1, tab2, tab3, tab4, tab7 = st.tabs(["💸 Blended Finance", "📊 WACC", "🥇Comparison", "🌐 Timeseries download", "📝 About"])
#yearly_waccs = wacc_predictor.calculate_historical_waccs(year, technology)
with tab1:
    st.title("Weighted Cost of Capital")
    df, overall_cost, breakdown, underlying = wacc_estimator.calculate_weighted_average(shares_df=shares_df, year=year, technology=technology, 
                                                  country_code=country_selection, concessionality=concessionality, merchant_risk=merchant_risk, currency_risk=currency_risk)
    visualiser.show_source_average(df, overall=overall_cost)
    st.write(breakdown)

with tab2:
    visualiser.plot_cost_components_from_underlying(underlying, concessionality, merchant_risk=merchant_risk, currency_risk=currency_risk)
with tab3:
    all_countries_estimates = wacc_estimator.calculate_cost_of_capital(
        year,
        technology,
        all_codes,
        concessionality=concessionality,
        currency_risk=merchant_risk,
        merchant_risk=currency_risk,
        currency_risk_col="Currency_Risk_Premium"
    )
    instrument, source, selected_col, label = visualiser.select_finance_metric()
    if selected_col not in all_countries_estimates.columns:
        st.error(f"Column not found: {selected_col}")
    else:
        selected_country = visualiser.display_finance_map(
            df=all_countries_estimates,
            value_col=selected_col,
            value_label=label
        )
with tab4:
    st.header("Historical and Projected Estimates")
    options = ["Interest Rate Change", "Renewable Growth", "GDP Change"]
    options_mapping = {"Interest Rate Change": "interest_rate", "Renewable Growth": "renewable_targets", "GDP Change": "gdp_change"}
    if country_selection is not None:
        end_year=2025
        projection_assumptions = st.pills("Projection Assumptions", options, selection_mode="multi")
        for i in projection_assumptions:
            name = options_mapping.get(i)
            globals()[f"{name}"] = f"{name}"
        if "Interest Rate Change" not in projection_assumptions:
            interest_rate = None
            end_year=2034
        if "Renewable Growth" not in projection_assumptions:
            renewable_targets = None
            end_year=2034
        if "GDP Change" not in projection_assumptions:
            gdp_change = None
            end_year=2034
        #historical_country_data = wacc_predictor.year_range_wacc(start_year=2015, end_year=2023, 
                                                             #technology=technology, country=country_selection)
        #if len(projection_assumptions) > 0:
            #future_waccs = wacc_predictor.projections_wacc(end_year=2029, technology=technology, country=country_selection, 
                                                    #interest_rates=interest_rate, GDP_change=gdp_change, renewable_targets=renewable_targets)
            #historical_country_data = pd.concat([future_waccs, historical_country_data])
        #historical_country_data = historical_country_data.drop(columns = ["Debt_Share", "Equity_Cost", "Debt_Cost", "Tax_Rate", "Country code", "WACC"])
        #visualiser.plot_comparison_chart(historical_country_data)
        with st.spinner(text=f"Collating data for all years for {technology} for {country_select} (typically takes 5 seconds)...", show_time=True, width="content"):
            technology_df = wacc_estimator.calculate_technology_yearly(start_year=2001, end_year=2035, countries=[country_selection], technologies=[technology],
            concessionality=concessionality,
            currency_risk=merchant_risk,
            merchant_risk=currency_risk)
            technology_df["Technology"] = technology_df["Technology"].replace(visualiser.tech_dict_reverse)
            selected_technology_df = technology_df[["Year", "Country code", "CoD_International_Commercial",	"CoE_International_Commercial",	"CoD_International_Public",	"CoE_International_Public",	
                                                    "CoD_Domestic_Commercial","CoE_Domestic_Commercial", "CoD_Domestic_Public",	"CoE_Domestic_Public",	"Technology", "Risk_Free", "Local_Risk_Free"]]
            st.download_button(
            label="Download selected technology estimates",
            data=convert_for_download(selected_technology_df),
            file_name=f"{technology}-costsofcapital-"+ country_selection + ".csv",
            mime="text/csv",
            icon=":material/download:",
            key="all-national-WACC-selected-technology",
        )
        with st.spinner(text=f"Collating data for all years and technology combinations for {country_select} (typically takes 3-4 mins)...", show_time=True, width="content"):
            all_technologies_years = wacc_estimator.calculate_technology_yearly(start_year=2001, end_year=2035, countries=[country_selection], technologies=all_techs,
            concessionality=concessionality,
            currency_risk=merchant_risk,
            merchant_risk=currency_risk)
            all_technologies_years["Technology"] = all_technologies_years["Technology"].replace(visualiser.tech_dict_reverse)
            all_technologies_years = all_technologies_years[["Year", "Country code", "CoD_International_Commercial",	"CoE_International_Commercial",	"CoD_International_Public",	"CoE_International_Public",	
                                                    "CoD_Domestic_Commercial","CoE_Domestic_Commercial", "CoD_Domestic_Public",	"CoE_Domestic_Public",	"Technology", "Risk_Free", "Local_Risk_Free"]]
            st.download_button(
            label="Download all technology estimates",
            data=convert_for_download(all_technologies_years),
            file_name="all-technology-costsofcapital-"+ country_selection + ".csv",
            mime="text/csv",
            icon=":material/download:",
            key="all-national-WACC-all-technology",
        )
with tab7: 
    text = open('about.md').read()
    st.write(text)
    