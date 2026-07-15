import xarray as xr
import pandas as pd
import numpy as np
import streamlit as st
from wacc_calculator_v1 import WaccCalculator


class WaccEstimator:
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
        self.current_year = "2025"

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
        self.tech_mappings = self.calculator.tech_premiums[["TECH", "VARIABLE"]].set_index('TECH')['VARIABLE'].to_dict()


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


    def pull_CRP_data(self, years):

        # Extract generation data
        data = self.crp_data

        # Add in exception for when years are above 2025
        if int(years) > int(self.current_year):
            year_current = years
            years = self.current_year
        
        ## normalize input to list of strings
        if isinstance(years, (str, int)):
            year_list = [str(years)]
        else:
            year_list = [str(y) for y in years]

        cols = ["Country", "Country code"] + year_list
        data_subset = data[cols].copy()

        # rename year columns to CRP_<year>
        rename_map = {y: f"CRP_{y}" for y in year_list}
        data_subset = data_subset.rename(columns=rename_map)

        # Apply modification for years above 2025
        if int(years) > int(self.current_year):
            data_subset = self.calculate_future_crp_all(year_current, data_subset)
            data_subset = data_subset.rename(columns=lambda c: "CRP" if c.startswith("CRP_") else c)

        return data_subset

    def pull_CDS_data(self, years):

        # Extract generation data
        data = self.cds_data

        # Add in exception for when years are above 2025
        if int(years) > int(self.current_year):
            year_current = years
            years = self.current_year
        
        # normalize input to list of strings
        if isinstance(years, (str, int)):
            year_list = [str(years)]
        else:
            year_list = [str(y) for y in years]

        cols = ["Country", "Country code"] + year_list
        data_subset = data[cols].copy()

        # rename year columns to CRP_<year>
        rename_map = {y: f"CDS_{y}" for y in year_list}
        data_subset = data_subset.rename(columns=rename_map)

        # Apply modification for years above 2025
        if int(years) > int(self.current_year):
            data_subset = self.calculate_future_crp_all(year_current, data_subset)
            st.write(data_subset)
            data_subset = data_subset.rename(columns=lambda c: "CDS" if c.startswith("CDS_") else c)

        return data_subset


    def calculate_future_crp_all(self, year_str, crp):

        # Pull the GDP per capita data for the new and old year
        year_orig = year_str
        year_old = self.current_year
        if int(year_str) > 2029:
            year_str = "2029"
        new_GDP = self.imf_data.copy().rename(columns={year_str:"GDP_"+year_str})[["Country code", "GDP_"+year_str]]
        current_GDP = self.imf_data.copy().rename(columns={year_old:"GDP_" + year_old})[["Country code", "GDP_" + year_old]]

        # Merge onto the CRP
        crp_merged = crp.merge(new_GDP, how="left", on="Country code").merge(current_GDP, how="left", on="Country code")

        # Calculate the new CRP
        crp_merged["GDP_Change"] = (crp_merged["GDP_"+ year_orig] / crp_merged["GDP_" + year_old])
        crp_merged["GDP_Change"].clip(upper=1.25, lower=0.75, inplace=True)
        crp_merged["GDP_Change"].fillna(1, inplace=True)
        crp_merged["CRP_"+year_orig] = crp_merged["CRP_"+year_old] * (crp_merged["GDP_Change"]) ** (-0.15)
        crp = crp_merged.drop(columns=["CRP_"+year_old, "GDP_"+ year_orig, "GDP_" + year_old, "GDP_Change"])
        crp = crp.rename(columns={"CRP_"+year_old: "CRP"})

        return crp

    def calculate_future_cds_all(self, year_str, cds):

        # Pull the GDP per capita data for the new and old year
        year_orig = year_str
        year_old = self.current_year
        if int(year_str) > 2029:
            year_str = "2029"
        new_GDP = self.imf_data.copy().rename(columns={year_str:"GDP_"+year_str})[["Country code", "GDP_"+year_str]]
        current_GDP = self.imf_data.copy().rename(columns={year_old:"GDP_" + year_old})[["Country code", "GDP_" + year_old]]

        # Merge onto the CRP
        cds_merged = cds.merge(new_GDP, how="left", on="Country code").merge(current_GDP, how="left", on="Country code")

        # Calculate the new CRP
        cds_merged["GDP_Change"] = (cds_merged["GDP_"+ year_orig] / cds_merged["GDP_" + year_old])
        cds_merged["GDP_Change"].clip(upper=1.25, lower=0.75, inplace=True)
        cds_merged["GDP_Change"].fillna(1, inplace=True)
        cds_merged["CDS"] = cds_merged["CDS_"+year_old] * (cds_merged["GDP_Change"]) ** (-0.15)
        cds = cds_merged.drop(columns=["CDS_"+year_old, "GDP_"+ year_orig, "GDP_2025", "GDP_Change"])
        cds = cds.rename(columns={"CDS_"+year_old: "CDS"})
        st.write(cds)

        return cds



    def pull_generation_data_v2(self, year_str, technology):

        # Extract generation data
        generation_data = self.generation_data
        if int(year_str) > 2024:
            year_str = "2023"
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


    def calculate_financial_maturity(self, storage_df, out_col="Immaturity_Premium"):

        # Extract underlying GFDD data
        gfdd_column = "2020" if "2020" in self.gfdd_dcps.columns else 2020 if 2020 in self.gfdd_dcps.columns else "2020"
        gfdd_2020 = self.gfdd_dcps[[gfdd_column]].reset_index().rename(columns={"index": "Country code", gfdd_column: "gfdd_dcps_2020"})
        gfdd_2020["Country code"] = gfdd_2020["Country code"].astype(str)

        # Merge onto existing data
        storage_df = storage_df.merge(gfdd_2020, how="left", on="Country code")
        
        # ---- Quantiles from global GFDD distribution ----
        quantiles = gfdd_2020["gfdd_dcps_2020"].dropna()
        q25 = quantiles.quantile(0.1)
        q75 = quantiles.quantile(0.9)

        # Default = 3
        storage_df[out_col] = 3.0

        # If quantiles valid, apply vectorized piecewise formula
        if pd.notna(q25) and pd.notna(q75) and q75 > q25:
            x = storage_df["gfdd_dcps_2020"]

            high_mask = x >= q75
            low_mask = x <= q25
            mid_mask = x.notna() & (~high_mask) & (~low_mask)

            storage_df.loc[high_mask, out_col] = 0.0
            storage_df.loc[low_mask, out_col] = 3.0
            storage_df.loc[mid_mask, out_col] = np.clip(
                3.0 * (q75 - x.loc[mid_mask]) / (q75 - q25),
                0.0, 3.0
            )

        # optional cleanup
        storage_df = storage_df.drop(columns=["gfdd_dcps_2020"])

        return storage_df

    
    def calculate_maturity_tech_premium(
    self,
    df,
    technology,
    penetration_col="Penetration",
    maturity_col="Maturity",
    premium_col="Technology_Premium"
):

        out = df.copy()

        # --- Select boundaries/premiums for technology (fallback to Other) ---
        tech_boundaries = self.calculator.penetration_boundaries
        maturity_premiums = self.calculator.maturity_premiums

        if (tech_boundaries["TECH"] == technology).any():
            b = tech_boundaries.loc[tech_boundaries["TECH"] == technology].iloc[0]
            p = maturity_premiums.loc[maturity_premiums["TECH"] == technology].iloc[0]
        else:
            b = tech_boundaries.loc[tech_boundaries["TECH"] == "Other"].iloc[0]
            p = maturity_premiums.loc[maturity_premiums["TECH"] == "Other"].iloc[0]

        intermediate = float(b["INTERMEDIATE"])
        mature = float(b["MATURE"])

        maturity_premium = float(p["MATURE"])
        intermediate_premium = float(p["INTERMEDIATE"])  # optional, see note below
        immature_premium = float(p["IMMATURE"])

        # --- Ensure numeric penetration ---
        pen = pd.to_numeric(out[penetration_col], errors="coerce")

        # --- Maturity class vectorized ---
        cond_mature = pen > mature
        cond_intermediate = (pen > intermediate) & (pen <= mature)

        out[maturity_col] = np.select(
            [cond_mature, cond_intermediate],
            ["Mature", "Intermediate"],
            default="Immature"
        )

        # --- Linear interpolation for intermediate zone ---
        # Same formula you used:
        # ((maturity_premium - immature_premium)/(mature-intermediate))*(pen-intermediate)+immature_premium
        if mature > intermediate:
            inter_val = (
                (maturity_premium - immature_premium) / (mature - intermediate)
            ) * (pen - intermediate) + immature_premium
        else:
            # defensive fallback if boundaries are bad
            inter_val = np.nan

        # --- Tech premium vectorized ---
        out[premium_col] = np.where(
            cond_mature,
            maturity_premium,
            np.where(
                cond_intermediate,
                inter_val,
                immature_premium
            )
        )

        # Optional: keep NaN where penetration is NaN
        out.loc[pen.isna(), [maturity_col, premium_col]] = [np.nan, np.nan]

        # Extract relative premiums
        tech_premiums = self.calculator.tech_premiums

        # Locate the value of the tech premium
        if tech_premiums["TECH"].isin([technology]).any():
            relative_premium = tech_premiums.loc[tech_premiums["TECH"]==technology]["PREMIUM"].values[0]
        else:
            relative_premium = tech_premiums.loc[tech_premiums["TECH"]=="Other"]["PREMIUM"].values[0]

        # Calculate relative technology premium
        if technology not in ["Wind", "Wind Offshore", "Solar"]:
            out[premium_col] = out[premium_col] + relative_premium

        return out
    
    def calculate_tech_risk(self, df, technology, year):

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
        

        # Extract Generation Data
        variable = str(self.tech_mappings.get(technology))
        if variable == "Other":
            ember_name = "Solar"
        else:
            ember_name = variable
        generation_data = self.pull_generation_data_v2(year, ember_name)
        previous_year = self.pull_generation_data_v2(str(int(year)-1), ember_name)
        generation_data = fill_missing_RE_values(generation_data, previous_year, int(year))
        generation_data = pd.merge(self.crp_data['Country code'],generation_data[['Country code', 'Penetration_'+year]], on="Country code", how="left")
        generation_data.fillna(0, inplace=True)
        generation_data = generation_data[['Country code', 'Penetration_'+year]]
        
        generation_data.rename(columns={"Penetration_"+year:"Penetration"}, inplace=True)
        if technology == "Other":
            generation_data["Penetration"] = generation_data["Penetration"] * 0

        # Merge on based on country code
        df = df.merge(generation_data, how="left", on="Country code")
        df["Penetration"].fillna(0, inplace=True)
        df = self.calculate_maturity_tech_premium(df, technology)

        # Drop unneeded column
        df = df.drop(columns=["Penetration"])

        return df

    def convert_currencies_usd_to_local_df_one_year(self, df, year, value_col="Risk_Free", country_col="Country code", output_col="Local_Risk_Free"):
        """
        Convert global risk free rate into local risk free rates
        """

        y = int(year)
        fwd_y = min(y, 2025)

        out = df.copy()
        out[country_col] = out[country_col].astype(str)

        # ---------- inflation prep ----------
        infl = self.calculator.inflation.copy()
        infl["Country code"] = infl["Country code"].astype(str)

        usd_row = infl.loc[infl["Country code"] == "USA"]
        if usd_row.empty:
            out[output_col] = np.nan
            return out

        needed_infl_cols = [str(fwd_y + k) for k in range(5)] + [str(y - 4 + k) for k in range(5)]
        missing_infl = [c for c in needed_infl_cols if c not in infl.columns]
        if missing_infl:
            out[output_col] = np.nan
            return out

        # Local forward and historical compounded inflation (vectorized across countries)
        local_fwd_vals = infl[[str(fwd_y + k) for k in range(5)]].apply(pd.to_numeric, errors="coerce").to_numpy()
        local_hist_vals = infl[[str(y - 4 + k) for k in range(5)]].apply(pd.to_numeric, errors="coerce").to_numpy()

        local_fwd = np.nanprod((100.0 + local_fwd_vals) / 100.0, axis=1) ** (1 / 5) - 1
        local_hist = np.nanprod((100.0 + local_hist_vals) / 100.0, axis=1) ** (1 / 5) - 1

        # USD forward/historical (single values)
        usd_fwd_vals = pd.to_numeric(
            usd_row[[str(fwd_y + k) for k in range(5)]].iloc[0], errors="coerce"
        ).to_numpy()
        usd_hist_vals = pd.to_numeric(
            usd_row[[str(y - 4 + k) for k in range(5)]].iloc[0], errors="coerce"
        ).to_numpy()

        usd_fwd = np.nanprod((100.0 + usd_fwd_vals) / 100.0) ** (1 / 5) - 1
        usd_hist = np.nanprod((100.0 + usd_hist_vals) / 100.0) ** (1 / 5) - 1

        # ---------- FX prep ----------
        fx = self.calculator.exchange_rates.copy()
        fx["Country code"] = fx["Country code"].astype(str)

        er_now_col = f"ER_{y}"
        er_past_col = f"ER_{y-4}"
        if er_now_col not in fx.columns or er_past_col not in fx.columns:
            out[output_col] = np.nan
            return out

        fx["er_now"] = pd.to_numeric(fx[er_now_col], errors="coerce")
        fx["er_past"] = pd.to_numeric(fx[er_past_col], errors="coerce")
        fx["depreciation"] = fx["er_now"] / fx["er_past"]

        # ---------- build per-country factor ----------
        factors = infl[["Country code"]].copy()
        factors["local_fwd"] = local_fwd
        factors["local_hist"] = local_hist

        factors = factors.merge(
            fx[["Country code", "depreciation"]],
            on="Country code",
            how="left"
        )

        ppp_implied = (1.0 + factors["local_hist"]) / (1.0 + usd_hist)
        expected_fx_dep = factors["depreciation"] / ppp_implied - 1.0

        factors["usd_to_local_factor"] = (
            (1.0 + factors["local_fwd"]) / (1.0 + usd_fwd)
        ) * (1.0 + expected_fx_dep)

        eu_iso3 = [
        "AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN",
        "FRA", "DEU", "GRC", "HUN", "IRL", "ITA", "LVA", "LTU", "LUX",
        "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE"
    ]
        out["fx_country_key"] = np.where(out[country_col].isin(eu_iso3), "EUR", out[country_col])

        factors_merge = factors[["Country code", "usd_to_local_factor"]].copy()
        factors_merge = factors_merge.rename(columns={"Country code": "fx_country_key"})


        # ---------- merge and convert ----------
        out = out.merge(
            factors_merge,
            on="fx_country_key",
            how="left"
        )

        v = pd.to_numeric(out[value_col], errors="coerce")
        f = pd.to_numeric(out["usd_to_local_factor"], errors="coerce")
        out[output_col] = (1.0 + v) * f - 1.0

        return out

    def estimate_currency_risk_premium_df(
    self,
    df,
    year,
    country_col="Country code",
    lookback=5,
    risk_aversion=0.1,
    output_col="Currency_Risk"
):
        """
        Vectorized currency risk premium for all countries in df[country_col].
        Returns df with output_col added.
        """

        out = df.copy()
        out[country_col] = out[country_col].astype(str)

        # Optional EUR mapping for EU rows (without changing country_col)
        eu_iso3 = [
            "AUT","BEL","BGR","HRV","CYP","CZE","DNK","EST","FIN","FRA","DEU","GRC",
            "HUN","IRL","ITA","LVA","LTU","LUX","MLT","NLD","POL","PRT","ROU","SVK",
            "SVN","ESP","SWE"
        ]
        out["fx_country_key"] = np.where(out[country_col].isin(eu_iso3), "EUR", out[country_col])

        y = int(year)
        obs_years = list(range(y - lookback + 1, y + 1))
        infl_cols = [str(n) for n in obs_years]
        er_prev_cols = [f"ER_{n-1}" for n in obs_years]
        er_curr_cols = [f"ER_{n}" for n in obs_years]

        # Validate columns
        miss_infl = [c for c in infl_cols if c not in self.calculator.inflation.columns]
        miss_er_prev = [c for c in er_prev_cols if c not in self.calculator.exchange_rates.columns]
        miss_er_curr = [c for c in er_curr_cols if c not in self.calculator.exchange_rates.columns]
        if miss_infl:
            raise ValueError(f"Missing inflation column(s): {miss_infl}")
        if miss_er_prev or miss_er_curr:
            raise ValueError(f"Missing exchange-rate column(s): {miss_er_prev + miss_er_curr}")

        # Country subset needed
        countries_needed = out["fx_country_key"].dropna().unique()

        infl = self.calculator.inflation.copy()
        infl["Country code"] = infl["Country code"].astype(str)

        fx = self.calculator.exchange_rates.copy()
        fx["Country code"] = fx["Country code"].astype(str)

        local_infl = infl.loc[infl["Country code"].isin(countries_needed), ["Country code"] + infl_cols].copy()
        local_fx = fx.loc[fx["Country code"].isin(countries_needed), ["Country code"] + er_prev_cols + er_curr_cols].copy()

        # USD inflation vector
        usd_row = infl.loc[infl["Country code"] == "USA", infl_cols]
        if usd_row.empty:
            raise ValueError("No inflation data found for hard currency country code 'USA'")
        usd_infl = pd.to_numeric(usd_row.iloc[0], errors="coerce").to_numpy(dtype=float) / 100.0  # shape (lookback,)
        st.write(usd_infl)

        # Build matrices
        local_infl_mat = local_infl.set_index("Country code")[infl_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float) / 100.0
        prev_mat = local_fx.set_index("Country code")[er_prev_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        curr_mat = local_fx.set_index("Country code")[er_curr_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)

        # Align country order (important)
        countries_infl = local_infl["Country code"].values
        countries_fx = local_fx["Country code"].values
        common = pd.Index(countries_infl).intersection(pd.Index(countries_fx))

        if len(common) == 0:
            out[output_col] = np.nan
            out.drop(columns=["fx_country_key"], inplace=True)
            return out

        local_infl_idx = local_infl.set_index("Country code").loc[common, infl_cols]
        local_fx_prev_idx = local_fx.set_index("Country code").loc[common, er_prev_cols]
        local_fx_curr_idx = local_fx.set_index("Country code").loc[common, er_curr_cols]

        li = local_infl_idx.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float) / 100.0
        ep = local_fx_prev_idx.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        ec = local_fx_curr_idx.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)

        # Vectorized formulas
        c_infl = ((1.0 + li) / (1.0 + usd_infl)) - 1.0
        c_dep = (ec - ep) / ep
        c_exc = c_dep - c_infl

        # std across years per country
        std_exc = np.nanstd(c_exc, axis=1, ddof=1)
        premium = risk_aversion * std_exc

        prem_tbl = pd.DataFrame({
            "fx_country_key": common.values,
            output_col: premium
        })

        out = out.merge(prem_tbl, on="fx_country_key", how="left")
        out.drop(columns=["fx_country_key"], inplace=True)

        return out

    def calculate_underlying_factors(self, year, technology, country_codes):

        # Produce a storage dataframe
        year = str(year)
        storage_df = pd.DataFrame(data={"Country code": country_codes, "Year": [year] * len(country_codes)})
        
        # Extract risk free rate
        rf_rate = self.ir_data[self.ir_data['Country code'] == "USA"][year].values[0].astype(float)
        storage_df["Risk_Free"] = rf_rate

        # Calculate local risk free rate
        storage_df = self.convert_currencies_usd_to_local_df_one_year(storage_df, year)
        storage_df["Local_Risk_Free"] = storage_df["Local_Risk_Free"].fillna(rf_rate)

        # Extract country default spread and cds
        crps = self.pull_CRP_data(year)
        cds = self.pull_CDS_data(year)
        storage_df = storage_df.merge(crps, how="left", on="Country code").merge(cds, how="left", on=["Country", "Country code"])

        # Rename country factors
        storage_df = storage_df.rename(columns={"CDS_"+str(year):"CDS", "CRP_"+str(year):"CRP"},)
        storage_df = storage_df.rename(columns={"CDS_2025":"CDS", "CRP_2025":"CRP"})

        # Get equity risk premium
        if int(year) > int(self.current_year):
            year = "2025"
        erp = crps.loc[crps['Country code']=="ERP"]["CRP_"+year][0].astype(float)
        storage_df["ERP"] = erp

        # Set lenders margin and merchant risk
        storage_df["Lenders_Margin"] = self.calculator.lenders_margin

        # Calculate currency risk
        #storage_df = self.estimate_currency_risk_premium_df(storage_df, year)

        # Calculate financial immaturity premium
        storage_df = self.calculate_financial_maturity(storage_df)

        # Calculate technology risk
        if int(year) > int(self.current_year)-1:
            year = "2024"
        storage_df = self.calculate_tech_risk(storage_df, technology, year)

        return storage_df

    def calculate_cost_of_capital(
        self,
        year,
        technology,
        country_codes,
        concessionality="Commercial Rate",
        currency_risk=False,
        merchant_risk=False,
        currency_risk_col="Currency_Risk_Premium"
    ):

        # Extract underlying data
        underlying_data = self.calculate_underlying_factors(year, technology, country_codes)
        data = underlying_data.copy()

        # Set factors
        equity_weighting = 1.35
        merchant_risk_value = 2.0 if merchant_risk else 0.0
        merchant_risk_weighting = 1.5
        conc = 0.0 if concessionality == "Commercial Rate" else float(concessionality)
        local_country_passthrough = 0.75
        int_country_passthrough = 0.51

        # Check if currency risk included
        if currency_risk and currency_risk_col in data.columns:
            crfx = pd.to_numeric(data[currency_risk_col], errors="coerce").fillna(0.0)
        else:
            crfx = 0.0

        # Extract all base terms
        riskfree_g = pd.to_numeric(data["Risk_Free"], errors="coerce").fillna(0.0)
        riskfree_l = pd.to_numeric(data["Local_Risk_Free"], errors="coerce").fillna(riskfree_g)
        cds = pd.to_numeric(data["CDS"], errors="coerce").fillna(0.0)
        erp = pd.to_numeric(data["ERP"], errors="coerce").fillna(0.0)
        tp = pd.to_numeric(data["Technology_Premium"], errors="coerce").fillna(0.0)
        lm = pd.to_numeric(data["Lenders_Margin"], errors="coerce").fillna(0.0)

        # Store concessionality
        data["Concessionality"] = conc * -1

        # -------------------------
        # International Commercial
        # -------------------------
        data["CoD_International_Commercial"] = (
            riskfree_g + int_country_passthrough*cds + tp + merchant_risk_value + crfx
        )
        data["CoE_International_Commercial"] = (
            riskfree_g + erp + int_country_passthrough * cds * equity_weighting + tp + merchant_risk_value * merchant_risk_weighting + crfx
        )

        # -------------------------
        # International Public
        # -------------------------
        data["CoD_International_Public"] = (
            riskfree_g + int_country_passthrough * cds + tp - conc + merchant_risk_value + crfx
        )
        data["CoE_International_Public"] = (
            riskfree_g + erp + int_country_passthrough * cds * equity_weighting + tp - conc + merchant_risk_value * merchant_risk_weighting + crfx
        )

        # -------------------------
        # Domestic Commercial
        # -------------------------
        data["CoD_Domestic_Commercial"] = (
            riskfree_l  + local_country_passthrough * cds + tp + lm + merchant_risk_value
        )
        data["CoE_Domestic_Commercial"] = (
            riskfree_l + erp + local_country_passthrough * cds * equity_weighting + tp + lm + merchant_risk_value * merchant_risk_weighting
        )

        # -------------------------
        # Domestic Public
        # -------------------------
        data["CoD_Domestic_Public"] = (
            riskfree_g + cds
        )
        data["CoE_Domestic_Public"] = (
            riskfree_g + cds * equity_weighting
        )

        # -------------------------
        # Grant
        # -------------------------
        data["CoD_Grant"] = 0.0
        data["CoE_Grant"] = 0.0

        return data

    def calculate_technology_yearly(self, start_year, end_year, countries, technologies, concessionality, currency_risk=None, merchant_risk=None):

        # Specify range
        year_range = np.arange(start_year, end_year+1, 1)
        storage_frames = []

        # Loop across year_range and technologies
        for tech in technologies:
            for year in year_range:
                # Calculate yearly WACC
                if int(year) < 2025:
                    yearly_wacc = self.calculate_cost_of_capital(year, tech, countries, concessionality=concessionality,
                                                                 currency_risk=currency_risk, merchant_risk=merchant_risk)
                #else:
                    #yearly_wacc = self.calculate_future_wacc(year, tech, countries)
                yearly_wacc = yearly_wacc.copy()
                yearly_wacc["Year"] = int(year)
                yearly_wacc["Technology"] = tech

                # Append storage frames with the yearly wacc output
                storage_frames.append(yearly_wacc)

        if not storage_frames:
            return pd.DataFrame()

        return pd.concat(storage_frames, ignore_index=True)

    
    

    def calculate_weighted_average(
    self,
    shares_df,
    year,
    technology,
    country_code,
    concessionality,
    merchant_risk=None,
    currency_risk=None
):

        # Check concessionality input
        if concessionality is None:
            concessionality = "Commercial Rate"

        shares_df = shares_df.copy()
        shares_df["Share"] = pd.to_numeric(shares_df["Share"], errors="coerce").fillna(0.0)
        shares_df["Debt_Share"] = pd.to_numeric(shares_df["Debt_Share"], errors="coerce").fillna(0.0).clip(0, 100)

        # -------------------------
        # 1) Get CoD / CoE per source from underlying factors
        # -------------------------
        # calculate_cost_of_capital returns for the selected country/technology
        cost_df = self.calculate_cost_of_capital(
            year=year,
            technology=technology,
            country_codes=[country_code],
            concessionality=concessionality,
            currency_risk=bool(currency_risk),
            merchant_risk=bool(merchant_risk),
            currency_risk_col="Currency_Risk_Premium"
        )

        if cost_df.empty:
            return shares_df, np.nan, pd.DataFrame()

        row = cost_df.iloc[0]

        # tax rate for WACC
        tax_rate = float(pd.to_numeric(row.get("Tax_Rate", 0.0), errors="coerce")) / 100.0

        # -------------------------
        # 2) Map source -> CoD / CoE
        # -------------------------
        source_to_cols = {
            "International Commercial": ("CoD_International_Commercial", "CoE_International_Commercial"),
            "International Public": ("CoD_International_Public", "CoE_International_Public"),
            "Domestic Commercial": ("CoD_Domestic_Commercial", "CoE_Domestic_Commercial"),
            "Domestic Public": ("CoD_Domestic_Public", "CoE_Domestic_Public"),
            "Grant": ("CoD_Grant", "CoE_Grant"),
        }

        shares_df["Cost_of_Debt"] = 0.0
        shares_df["Cost_of_Equity"] = 0.0
        shares_df["Cost_of_Capital"] = 0.0

        for src, (cod_col, coe_col) in source_to_cols.items():
            mask = shares_df["source"] == src
            if not mask.any():
                continue

            cod = float(pd.to_numeric(row.get(cod_col, 0.0), errors="coerce"))
            coe = float(pd.to_numeric(row.get(coe_col, 0.0), errors="coerce"))

            d = float(shares_df.loc[mask, "Debt_Share"].values[0]) / 100.0  # source-specific debt share
            wacc_src = (1.0 - tax_rate) * cod * d + (1.0 - d) * coe

            # force grant to zero if desired
            if src == "Grant":
                cod, coe, wacc_src = 0.0, 0.0, 0.0

            shares_df.loc[mask, "Cost_of_Debt"] = cod
            shares_df.loc[mask, "Cost_of_Equity"] = coe
            shares_df.loc[mask, "Cost_of_Capital"] = wacc_src

        # -------------------------
        # 3) Overall weighted cost of capital
        # -------------------------
        total_share = shares_df["Share"].sum()
        if total_share > 0:
            weights = shares_df["Share"] / total_share
            overall_cost = float((weights * shares_df["Cost_of_Capital"]).sum())
        else:
            overall_cost = np.nan

        # Optional contribution columns
        shares_df["Debt_Contribution"] = shares_df["Share"] * shares_df["Debt_Share"] / 100.0
        shares_df["Equity_Contribution"] = shares_df["Share"] * (100.0 - shares_df["Debt_Share"]) / 100.0

        # -------------------------
        # 4) Build a simple breakdown table (source-level)
        # -------------------------
        breakdown = shares_df[[
            "source", "Share", "Debt_Share",
            "Cost_of_Debt", "Cost_of_Equity", "Cost_of_Capital",
            "Debt_Contribution", "Equity_Contribution"
        ]].copy()

        breakdown["Country code"] = country_code
        breakdown["Technology"] = technology
        breakdown["Year"] = year
        breakdown["Tax_Rate"] = tax_rate * 100.0

        return shares_df, overall_cost, breakdown, cost_df
    

