import xarray as xr
import pandas as pd
import numpy as np
import streamlit as st
from wacc_calculator_v1 import WaccCalculator


class WaccPredictor:
    def __init__(self, crp_data, generation_data, GDP, tax_data, ember_targets, us_ir, imf_data, collated_crp_cds):
        """ Initialises the WACC Predictor Class, which is used to generate an estimate of the cost of capital at
         a national level for countries with available data
        
        Inputs:
        Data_path - path direction to Data inputs
        Generation_Data - Ember Yearly Generation Data for 2000-2023
        CRP_Data - Data on Country Risk Premiums, taken from Damodaran for multiple years.
        Country_codes - Country coding to ISO 3 codes
        GDP - GDP per capita data
        Tax_Data - Corporate Tax Rates for individual countries by year
        RF_rate - Risk free rates on a yearly basis
        Ember_targets - Targets for 2030 selected from Ember
        US_IR - Projections of the U.S. long term interest rates conducted by the CBO alongside OECD IR data
        IMF_data - Projections for GDP per capita from the IMF's WEO
        Collated_crp_cds - Data from Damodaran containing Country Risk Premiums and Ratings-based default spreads

        
        """
    
        # Read in relevant inputs
        self.crp_data = pd.read_csv(crp_data)
        self.generation_data = pd.read_csv(generation_data)
        self.gdp_data = pd.read_csv(GDP)
        self.tax_data = pd.read_csv(tax_data)
        self.imf_data = pd.read_csv(imf_data)
        self.ember_targets = pd.read_csv(ember_targets)

        # Read in crp data
        self.crp_data = pd.read_excel(collated_crp_cds, sheet_name="CRP", header=0)
        self.cds_data = pd.read_excel(collated_crp_cds, sheet_name="CDS", header=0)
        self.crp_data.columns = self.crp_data.columns.astype("str")
        self.cds_data.columns = self.cds_data.columns.astype("str")

        # Read in GFDD data
        self.gfdd_data = pd.read_csv("./DATA/GFDD_2022_Extract.csv")
        self.process_gfdd_data()

        # Fix corporate tax data
        self.tax_data = self.tax_data.replace(to_replace="NA", value=0)

        # Read in projections of data
        self.renewable_projections = pd.read_csv(ember_targets)
        self.ir_data = pd.read_csv(us_ir)

        # Call WaccCalculator Object
        self.calculator = WaccCalculator(tech_premiums="./DATA/TechPremiums.csv", penetration_boundaries="./DATA/TechBoundaries.csv", maturity_premiums="./DATA/MaturityPremiums.csv", 
                                         exchange_rates="./DATA/ExchangeRates.csv", inflation="./DATA/IMF_Inflation_Rates.csv")

        # Get technologies
        self.technologies = self.calculator.tech_premiums["TECH"].values


    def process_gfdd_data(self):

        # Extract needed columns
        selected_df = self.gfdd_data[["Country code", "Year", "Private_credit_by_deposit", "Domestic_Credit_Private_Sector", "Domestic_Debt_GDP"]]

        # Reshape so that year is the variable
        self.gfdd_pcd = selected_df[["Country code", "Year", "Private_credit_by_deposit"]].pivot_table(values="Private_credit_by_deposit", 
                                                                                                       index="Country code", columns="Year")
        self.gfdd_dcps = selected_df[["Country code", "Year", "Domestic_Credit_Private_Sector"]].pivot_table(values="Domestic_Credit_Private_Sector", 
                                                                                                       index="Country code", columns="Year")
        self.gfdd_debt = selected_df[["Country code", "Year", "Domestic_Debt_GDP"]].pivot_table(values="Domestic_Debt_GDP", 
        index="Country code", columns="Year")

        

    def calculate_historical_waccs(self, year, technology):

        def fill_missing_RE_values(data, previous_year, year):

            # Set Country Code as index
            data.set_index('Country code', inplace=True)
            previous_year.set_index('Country code', inplace=True)

            # Fill missing values for 2023 with 2022 data
            data = pd.merge(data, previous_year, on="Country code", how="left")
            data['Penetration_' + str(year)] = data['Penetration_' + str(year)].fillna(data['Penetration_'+str(year-1)])

            # Reset index if needed
            data.reset_index(inplace=True)

            return data
        
        # Convert year into a string
        year_str = str(year)
        year_int = int(year)

        # Extract long term U.S. interest rates (proxy for risk free rate)
        rf_rate = self.ir_data[self.ir_data['Country code'] == "USA"][year_str].values[0].astype(float)

        # Extract CRPs
        crps = self.pull_CRP_data(year_str)
        cds = self.pull_CDS_data(year_str)
        erp = crps[crps['Country code']=="ERP"]["CRP_"+year_str][0]
        crp_data = crps
        cds_data = cds

        # Extract Generation Data
        if any(technology in s for s in ["Wave", "Tidal", "Geothermal", "Gas CCUS"]):
            ember_name = "Other Renewables"
        elif technology == "Wind Offshore":
            ember_name = "Wind" 
            ## PLACEHOLDER TO ADD IN DATA ON OFFSHORE WIND IN EUROPE FROM EMBERS DATA
        else:
            ember_name = technology
        generation_data = self.pull_generation_data_v2(year_str, ember_name)
        previous_year = self.pull_generation_data_v2(str(year_int-1), ember_name)
        generation_data = fill_missing_RE_values(generation_data, previous_year, year_int)
        generation_data = pd.merge(self.crp_data['Country code'],generation_data[['Country code', 'Penetration_'+year_str]], on="Country code", how="left")
        generation_data.fillna(0, inplace=True)
        generation_data.rename(columns={"Penetration_"+year_str:"Penetration"}, inplace=True)
        if technology == "Gas CCUS":
            generation_data["Penetration"] = generation_data["Penetration"] * 0


        # Extract Tax Rates
        tax_rate = pd.merge(self.crp_data['Country code'], self.tax_data[['Country code', year_str]], on="Country code", how="left")
        tax_rate["Tax_Rate"] = tax_rate[year_str]
        tax_rate['Tax_Rate'] = tax_rate['Tax_Rate'].fillna(value=0)
        tax_data = tax_rate
                           

        # Calculate WACC and contributions
        results = self.calculator.calculate_country_wacc(rf_rate=rf_rate, crp=crp_data, cds=cds_data, tax_rate=tax_data, technology=technology, year=year_str, erp=erp,
                                            tech_penetration=generation_data)
        
        # Clean results
        results = results.dropna(thresh=11)

        return results

    def pull_CRP_data(self, year):

        
        # Extract generation data
        data = self.crp_data
        
        # Extract specific year
        data_subset = data[["Country", "Country code", year]]
        data_subset = data_subset.rename(columns={year: "CRP_"+year})
        
        
        return data_subset

    def pull_CDS_data(self, year):

        
        # Extract generation data
        data = self.cds_data
        
        # Extract specific year
        data_subset = data[["Country", "Country code", year]]
        data_subset = data_subset.rename(columns={year: "CDS_"+year})
        
        
        return data_subset
    

    def pull_generation_data_v2(self, year_str, technology):

        
        # Extract generation data
        generation_data = self.generation_data
        if year_str == "2024":
            year = "2023"
        year = int(year_str)
        
        # Extract Capacity
        capacity_subset = generation_data[(generation_data['Year'] == year) & (generation_data['Category'] == "Capacity") & (generation_data['Unit'] == "GW")]                                             
        capacity_data = capacity_subset[capacity_subset['Variable'] == technology]
        capacity_data = capacity_data.rename(columns = {"Value" : "Capacity_" + year_str, "YoY absolute change": "Capacity_" + year_str + "_YoY_Change"})

        
        # Extract Penetration
        penetration_subset = generation_data[(generation_data['Year'] == year) & (generation_data['Category'] ==  "Electricity generation") & (generation_data['Unit'] == "%")]  
        penetration_data = penetration_subset[penetration_subset['Variable'] == technology]
        penetration_data = penetration_data.rename(columns = {"Value" : "Penetration_" + year_str, "YoY absolute change": "Penetration_" + year_str + "_YoY_Change"})

        
        # Extract needed data
        penetration_data = penetration_data[["Area", "Country code", "Year", "Continent", "Penetration_" + year_str,"Penetration_" + year_str + "_YoY_Change"]]
        capacity_data  = capacity_data[["Country code", "Capacity_" + year_str, "Capacity_" + year_str + "_YoY_Change"]]
        data_for_output = pd.merge(penetration_data, capacity_data, on="Country code", how="outer")

        # Extract only data that is present in the CRP dataset
        data_for_output = pd.merge(self.crp_data['Country code'], data_for_output, how="left", on="Country code")
        
        return data_for_output


    def year_range_wacc(self, start_year, end_year, technology, country):

        # Specify range
        year_range = np.arange(start_year, end_year+1, 1)

        # Loop across year_range
        for year in year_range:

            # Calculate yearly WACC
            yearly_wacc = self.calculate_yearly_wacc(year, technology, country)
            yearly_wacc["Year"] = int(year)

            # Concat
            if year == start_year:
                storage_df = yearly_wacc
            else:
                storage_df = pd.concat([storage_df, yearly_wacc])


        return storage_df
    

    def projections_wacc(self, end_year, technology, country, interest_rates=None, GDP_change=None, renewable_targets=None):

        # Specify range
        year_range = np.arange(2025, end_year+1, 1)

        # Loop across year_range
        for year in year_range:

            # Calculate yearly WACC
            yearly_wacc = self.calculate_future_wacc(year, technology, country, interest_rates=interest_rates, GDP_change=GDP_change, renewable_targets=renewable_targets)
            yearly_wacc["Year"] = int(year)

            # Concat
            if year == 2025:
                storage_df = yearly_wacc
            else:
                storage_df = pd.concat([storage_df, yearly_wacc])


        return storage_df

    def calculate_future_wacc(self, year, technology, country_code,  interest_rates=None, GDP_change=None, renewable_targets=None):
        
        def fill_missing_RE_values(data, previous_year, year):

            # Set Country Code as index
            data.set_index('Country code', inplace=True)
            previous_year.set_index('Country code', inplace=True)

            # Fill missing values for 2023 with 2022 data
            data = pd.merge(data, previous_year, on="Country code", how="left")
            data['Penetration_' + str(year)] = data['Penetration_' + str(year)].fillna(data['Penetration_'+str(year-1)])

            # Reset index if needed
            data.reset_index(inplace=True)

            return data

        # Convert year into a string
        year_str = str(year)
        year_int = int(year)
        year_old = str(2024)

        # Extract long term U.S. interest rates (proxy for risk free rate)
        if interest_rates is not None:
            rf_rate = self.ir_data[self.ir_data['Country code'] == "USA"][year_str].values[0].astype(float)
        else:
            rf_rate = self.ir_data[self.ir_data['Country code'] == "USA"][year_old].values[0].astype(float)

        # Extract CRPs
        if GDP_change is not None:
            old_crp = self.pull_CRP_data(year_old)
            old_cds = self.pull_CDS_data(year_old)
            crps = self.calculate_future_crp(year_str=year_str, year_old=year_old, crp=old_crp, country_code=country_code)
            cds = self.calculate_future_cds(year_str=year_str, year_old=year_old, cds=old_cds, country_code=country_code)
        else:
            crps = self.pull_CRP_data(year_old)
            cds = self.pull_CDS_data(year_old)
            crps = crps.rename(columns={"CRP_" + year_old: "CRP_"+year_str})
            cds = crps.rename(columns={"CDS_" + year_old: "CDS_"+year_str})
        crp_data = crps.loc[crps["Country code"] == country_code, "CRP_"+year_str].values[0]
        cds_data = cds.loc[cds["Country code"] == country_code, "CDS_"+year_str].values[0]
        
        

        # Get ERP data
        erps = self.pull_CRP_data(year_old)
        erp = erps.loc[erps['Country code']=="ERP"]["CRP_"+year_old][0].astype(float)
        

        # Extract Generation Data 
        if any(technology in s for s in ["Wave", "Tidal", "Geothermal", "Gas CCUS"]):
            ember_name = "Other Renewables"
        elif technology == "Wind Offshore":
            ember_name = "Wind" 
            ## PLACEHOLDER TO ADD IN DATA ON OFFSHORE WIND IN EUROPE FROM EMBERS DATA
        else:
            ember_name = technology
        generation_data = self.pull_generation_data_v2(year_str, ember_name)
        previous_year = self.pull_generation_data_v2(str(year_int-1), ember_name)
        generation_data = fill_missing_RE_values(generation_data, previous_year, year_int)
        generation_data = generation_data[['Country code', 'Penetration_'+year_str]]
        generation_data.fillna(0, inplace=True)
        generation_data.rename(columns={"Penetration_"+year_str:"Penetration"}, inplace=True)
        if technology == "Gas CCUS":
            generation_data["Penetration"] = generation_data["Penetration"] * 0

        # Select generation data for a given country
        generation_data = generation_data.loc[generation_data["Country code"] == country_code]

        # if year is above 2023, calculate generation using linear interpolation
        if renewable_targets is not None:
            generation_data = self.evaluate_future_penetration(generation_data, technology, country_code, year_str, year_old)


        # Extract Tax Rates
        tax_rate = pd.merge(self.crp_data['Country code'], self.tax_data[['Country code', year_old]], on="Country code", how="left")
        tax_rate["Tax_Rate"] = tax_rate[year_old]
        tax_rate['Tax_Rate'] = tax_rate['Tax_Rate'].fillna(value=0)
        tax_data = tax_rate.loc[tax_rate["Country code"] == country_code, "Tax_Rate"]
        
                           
                           

        # Calculate WACC and contributions
        results = self.calculator.calculate_wacc_individual(rf_rate=rf_rate, crp=crp_data, cds=cds_data, tax_rate=tax_data, technology=technology, year=year_str,erp=erp,
                                            tech_penetration=generation_data, country_code=country_code)
        

        return results

    def evaluate_future_penetration(self, generation_data, technology, country_code, year_str, year_old):

        # Extract renewable targets
        renewable_targets = self.ember_targets.loc[(self.ember_targets["Country code"] == country_code) & (self.ember_targets["fuel_category"] == technology) 
                                                   & (self.ember_targets["metric"] == "share_of_generation_pct")]

        # Check if renewable targets are present
        if renewable_targets.empty:
            return generation_data
        else:
            generation_data["Penetration"] = generation_data["Penetration"] + (int(year_str) - int(year_old)) * (renewable_targets["value"] - generation_data["Penetration"]) / (renewable_targets["target_year"].values[0] - int(year_old) )
        return generation_data
    
    def calculate_future_crp(self, year_str, year_old, crp, country_code):

        # Pull the GDP per capita data for the new and old year
        year_orig = year_str
        if year_str == "2030":
            year_str = "2029"
        try:
            new_GDP = self.imf_data.loc[self.imf_data["Country code"] == country_code, year_str].values[0]
            old_GDP = self.imf_data.loc[self.imf_data["Country code"] == country_code, year_old].values[0]
        except:
            new_GDP = 1
            old_GDP = 1
    

        # Calculate the new CRP
        if year_orig == "2030":
            year_str = year_orig
        crp["CRP_"+year_str] = crp["CRP_"+year_old] * (float(new_GDP) / float(old_GDP)) ** (-0.15)
        crp.drop(columns=["CRP_"+year_old], inplace=True)

        return crp

    def calculate_future_cds(self, year_str, year_old, cds, country_code):

        # Pull the GDP per capita data for the new and old year
        year_orig = year_str
        if year_str == "2030":
            year_str = "2029"
        try:
            new_GDP = self.imf_data.loc[self.imf_data["Country code"] == country_code, year_str].values[0]
            old_GDP = self.imf_data.loc[self.imf_data["Country code"] == country_code, year_old].values[0]
        except:
            new_GDP = 1
            old_GDP = 1

        # Calculate the new CDS
        if year_orig == "2030":
            year_str = year_orig
        cds["CDS_"+year_str] = cds["CDS_"+year_old] * (float(new_GDP) / float(old_GDP)) ** (-0.15)
        cds.drop(columns=["CDS_"+year_old], inplace=True)

        return cds


    def calculate_yearly_wacc(self, year, technology, country_code):

        def fill_missing_RE_values(data, previous_year, year):

            # Set Country Code as index
            data.set_index('Country code', inplace=True)
            previous_year.set_index('Country code', inplace=True)

            # Fill missing values for 2023 with 2022 data
            data = pd.merge(data, previous_year, on="Country code", how="left")
            data['Penetration_' + str(year)] = data['Penetration_' + str(year)].fillna(data['Penetration_'+str(year-1)])

            # Reset index if needed
            data.reset_index(inplace=True)

            return data
        
        # Convert year into a string
        year_str = str(year)
        year_int = int(year)


        # Extract long term U.S. interest rates (proxy for risk free rate)
        rf_rate = self.ir_data[self.ir_data['Country code'] == "USA"][year_str].values[0].astype(float)

        # Extract CRPs
        crps = self.pull_CRP_data(year_str)
        erps = crps.copy()
        erp = erps.loc[erps['Country code']=="ERP"]["CRP_"+year_str][0].astype(float)
        crp_data = crps.loc[crps["Country code"] == country_code, "CRP_"+str(year)]

        # Extract Cds
        cds = self.pull_CDS_data(year_str)
        cds_data = cds.loc[cds["Country code"] == country_code, "CDS_"+str(year)]


        # Extract Generation Data
        if any(technology in s for s in ["Wave", "Tidal", "Geothermal"]):
            ember_name = "Other Renewables"
        elif technology == "Wind Offshore":
            ember_name = "Wind" 
            ## PLACEHOLDER TO ADD IN DATA ON OFFSHORE WIND IN EUROPE FROM EMBERS DATA
        else:
            ember_name = technology
        generation_data = self.pull_generation_data_v2(year_str, ember_name)
        previous_year = self.pull_generation_data_v2(str(year_int-1), ember_name)
        generation_data = fill_missing_RE_values(generation_data, previous_year, year_int)
        generation_data = generation_data[['Country code', 'Penetration_'+year_str]]
        generation_data.fillna(0, inplace=True)
        generation_data.rename(columns={"Penetration_"+year_str:"Penetration"}, inplace=True)
        if technology == "Gas CCUS":
            generation_data["Penetration"] = generation_data["Penetration"] * 0

        

        # Select generation data for a given country
        generation_data = generation_data.loc[generation_data["Country code"] == country_code]




        # Extract Tax Rates
        tax_rate = pd.merge(self.crp_data['Country code'], self.tax_data[['Country code', year_str]], on="Country code", how="left")
        tax_rate["Tax_Rate"] = tax_rate[year_str]
        tax_rate['Tax_Rate'] = tax_rate['Tax_Rate'].fillna(value=0)
        tax_data = tax_rate.loc[tax_rate["Country code"] == country_code, "Tax_Rate"]
                           
                           

        # Calculate WACC and contributions
        results = self.calculator.calculate_wacc_individual(rf_rate=rf_rate, crp=crp_data, cds=cds_data, tax_rate=tax_data, technology=technology, year=year_str, erp=erp,
                                            tech_penetration=generation_data, country_code=country_code)

        return results
    

    def calculate_technology_wacc(self, year, country, technologies):


        # Loop across year_range
        for i, tech in enumerate(technologies):

            # Calculate yearly WACC
            tech_wacc = self.calculate_yearly_wacc(year, tech, country)
            tech_wacc["Year"] = int(year)
            tech_wacc["Technology"] = tech

            # Concat
            if i == 0:
                storage_df = tech_wacc
            else:
                storage_df = pd.concat([storage_df, tech_wacc])

        return storage_df
    

    def calculate_weighted_average(self, shares_df, year, technology, country_code, concessionality, merchant_risk=None, currency_risk=None):

        # Set concessionality
        if concessionality is None:
            concessionality = "Commercial Rate"
        
        # Ensure numeric columns
            shares_df = shares_df.copy()
            shares_df["Share"] = pd.to_numeric(shares_df["Share"], errors="coerce").fillna(0.0)
            shares_df["Debt_Share"] = pd.to_numeric(shares_df["Debt_Share"], errors="coerce").fillna(0.0)

        # Calculate the international commercial cost of capital and share
        if int(year) > 2024:
            commercial_results = self.calculate_future_wacc(year, technology, country_code,  
                                  interest_rates=True, GDP_change=True, renewable_targets=True)
        else:
            commercial_results = self.calculate_yearly_wacc(year, technology, country_code)


        # Calculate currency risk
        currency_risk_estimates = self.calculator.estimate_currency_risk_premium(country_code,year,lookback=10,risk_aversion=0.15)
        currency_risk_premium = currency_risk_estimates["currency_risk_premium"] * 100
        
        # Extract underlying parameters
        breakdown = self.calculate_cost_components(commercial_results, shares_df.source.values, concessionality,
                                                    currency_risk_premium, merchant_risk=merchant_risk, currency_risk=currency_risk, year=year, country_code=country_code)

        # Calculate the cost of capital from each source, first extract key parameters
        tax_rate= commercial_results["Tax_Rate"].values[0] / 100
        source_order = [
        "International Commercial",
        "International Public",
        "Domestic Commercial",
        "Domestic Public",
        "Grant",
        ]

        # Prepare output columns
        shares_df["Cost_of_Debt"] = 0.0
        shares_df["Cost_of_Equity"] = 0.0
        shares_df["Cost_of_Capital"] = 0.0

        for src in source_order:
            mask = shares_df["source"] == src
            if not mask.any():
                continue

            if src == "Grant":
                cost_debt = 0.0
                cost_equity = 0.0
                wacc_src = 0.0
            else:
                cost_debt = pd.to_numeric(breakdown.loc[f"Debt - {src}"], errors="coerce").sum()
                cost_equity = pd.to_numeric(breakdown.loc[f"Equity - {src}"], errors="coerce").sum()

                debt_share = float(shares_df.loc[mask, "Debt_Share"].values[0]) / 100.0
                debt_share = min(max(debt_share, 0.0), 1.0)

                wacc_src = (1.0 - tax_rate) * cost_debt * debt_share + (1.0 - debt_share) * cost_equity

            shares_df.loc[mask, "Cost_of_Debt"] = cost_debt
            shares_df.loc[mask, "Cost_of_Equity"] = cost_equity
            shares_df.loc[mask, "Cost_of_Capital"] = wacc_src
        

        # Calculate the overall cost of capital
        total_share = shares_df["Share"].sum()
        if total_share > 0:
            w = shares_df["Share"] / total_share
            overall_cost = float((w * shares_df["Cost_of_Capital"]).sum())
        else:
            overall_cost = np.nan

        shares_df["Debt_Contribution"] = shares_df["Share"] * shares_df["Debt_Share"] / 100.0
        shares_df["Equity_Contribution"] = shares_df["Share"] * (100.0 - shares_df["Debt_Share"]) / 100.0

        return shares_df, overall_cost, breakdown
    


    def calculate_cost_components(self, data, sources, concessionality, currency_risk_premium, year, country_code, currency_risk=None, merchant_risk=None):

        # Set up dataframe
        debt_cost_components_df = pd.DataFrame(index=sources, columns=[
            'Country code', 'Risk Free Rate', 'Country Risk Premium', 'Country Default Spread', 
            'Equity Risk Premium', 'Technology Risk Premium', 'Immaturity Premium', 'Concessionality', "Merchant Risk", 'Year'
        ])
        
        equity_cost_components_df = pd.DataFrame(index=sources, columns=[
            'Country code', 'Risk Free Rate', 'Country Risk Premium', 'Country Default Spread', 
            'Equity Risk Premium', 'Technology Risk Premium', 'Immaturity Premium', "Merchant Risk", 'Concessionality', 'Year'
        ])
        equity_weighting = 1.35
        if concessionality == "Commercial Rate":
            concessionality = 0
        if merchant_risk:
            merchant_risk = 2
        else:
            merchant_risk = 0
        merchant_risk_weighting = 1.5
        if currency_risk:
            currency_risk_premium = currency_risk_premium
        else:
            currency_risk_premium = 0

        # Convert from global to international risk free rate
        data["year"] = year
        data["Country_code"] = country_code
        data = self.calculator.convert_currencies_usd_to_local_df(df=data)

        
        # For each source, set the debt cost components
        for source in sources:
            if source == "International Commercial":
                debt_cost_components_df.loc[source, 'Country code'] = data["Country code"].values[0]
                debt_cost_components_df.loc[source, 'Risk Free Rate'] = data["Risk_Free"].values[0]
                debt_cost_components_df.loc[source, 'Country Default Spread'] = np.max([data["CDS"].values[0] - currency_risk_premium, 0])
                debt_cost_components_df.loc[source, 'Technology Risk Premium'] = data["Tech_Premium"].values[0]
                debt_cost_components_df.loc[source, 'Merchant Risk'] = merchant_risk
                debt_cost_components_df.loc[source, 'Currency Risk Premium'] = currency_risk_premium
            elif source == "International Public":
                debt_cost_components_df.loc[source, 'Country code'] = data["Country code"].values[0]
                debt_cost_components_df.loc[source, 'Risk Free Rate'] = data["Risk_Free"].values[0]
                debt_cost_components_df.loc[source, 'Country Default Spread'] = np.max([data["CDS"].values[0] - currency_risk_premium, 0])
                debt_cost_components_df.loc[source, 'Technology Risk Premium'] = data["Tech_Premium"].values[0]
                debt_cost_components_df.loc[source, 'Concessionality'] = -1 * float(concessionality)
                debt_cost_components_df.loc[source, 'Merchant Risk'] = merchant_risk
                debt_cost_components_df.loc[source, 'Currency Risk Premium'] = currency_risk_premium
            elif source == "Domestic Public":
                debt_cost_components_df.loc[source, 'Country code'] = data["Country code"].values[0]
                debt_cost_components_df.loc[source, 'Risk Free Rate'] = data["Risk_Free"].values[0]
                debt_cost_components_df.loc[source, 'Country Default Spread'] = data["CDS"].values[0]
            elif source == "Domestic Commercial":
                debt_cost_components_df.loc[source, 'Country code'] = data["Country code"].values[0]
                debt_cost_components_df.loc[source, 'Risk Free Rate'] = data["Local_Risk_Free"].values[0]
                debt_cost_components_df.loc[source, 'Country Default Spread'] = 0
                debt_cost_components_df.loc[source, 'Technology Risk Premium'] = data["Tech_Premium"].values[0]
                debt_cost_components_df.loc[source, 'Immaturity Premium'] = data["Lenders Margin"].values[0]
                debt_cost_components_df.loc[source, 'Merchant Risk'] = merchant_risk
        
        # For equity cost components
        for source in sources:
            if source == "International Commercial":
                equity_cost_components_df.loc[source, 'Country code'] = data["Country code"].values[0]
                equity_cost_components_df.loc[source, 'Risk Free Rate'] = data["Risk_Free"].values[0]
                equity_cost_components_df.loc[source, 'Equity Risk Premium'] = data["ERP"].values[0]
                equity_cost_components_df.loc[source, 'Country Default Spread'] = (np.nanmax([data["CDS"].values[0] - currency_risk_premium, 0]))* equity_weighting 
                equity_cost_components_df.loc[source, 'Technology Risk Premium'] = data["Tech_Premium"].values[0]
                equity_cost_components_df.loc[source, 'Merchant Risk'] = merchant_risk * merchant_risk_weighting
                equity_cost_components_df.loc[source, 'Currency Risk Premium'] = currency_risk_premium
            elif source == "International Public":
                equity_cost_components_df.loc[source, 'Country code'] = data["Country code"].values[0]
                equity_cost_components_df.loc[source, 'Risk Free Rate'] = data["Risk_Free"].values[0]
                equity_cost_components_df.loc[source, 'Country Default Spread'] = (data["CDS"].values[0] - currency_risk_premium)* equity_weighting 
                equity_cost_components_df.loc[source, 'Technology Risk Premium'] = data["Tech_Premium"].values[0]
                equity_cost_components_df.loc[source, 'Equity Risk Premium'] = data["ERP"].values[0]
                equity_cost_components_df.loc[source, 'Concessionality'] = -1 * float(concessionality)
                equity_cost_components_df.loc[source, 'Merchant Risk'] = merchant_risk * merchant_risk_weighting
                equity_cost_components_df.loc[source, 'Currency Risk Premium'] = currency_risk_premium
            elif source == "Domestic Public":
                equity_cost_components_df.loc[source, 'Country code'] = data["Country code"].values[0]
                equity_cost_components_df.loc[source, 'Risk Free Rate'] = data["Risk_Free"].values[0]
                equity_cost_components_df.loc[source, 'Country Default Spread'] = data["CDS"].values[0] * equity_weighting
            elif source == "Domestic Commercial":
                equity_cost_components_df.loc[source, 'Country code'] = data["Country code"].values[0]
                equity_cost_components_df.loc[source, 'Risk Free Rate'] = data["Local_Risk_Free"].values[0]
                equity_cost_components_df.loc[source, 'Country Default Spread'] = 0
                equity_cost_components_df.loc[source, 'Technology Risk Premium'] = data["Tech_Premium"].values[0]
                equity_cost_components_df.loc[source, 'Immaturity Premium'] = float(data["Lenders Margin"].values[0])
                equity_cost_components_df.loc[source, 'Equity Risk Premium'] = data["ERP"].values[0]
                equity_cost_components_df.loc[source, 'Merchant Risk'] = merchant_risk * merchant_risk_weighting

        # Merge the DataFrames with prefixed indices
        debt_cost_components_df.index = "Debt - " + debt_cost_components_df.index
        equity_cost_components_df.index = "Equity - " + equity_cost_components_df.index
        merged_cost_components_df = pd.concat([debt_cost_components_df, equity_cost_components_df])

        # Reshape so that year is the variable
        #st.write(self.gfdd_dcps)
        
        return merged_cost_components_df



    
