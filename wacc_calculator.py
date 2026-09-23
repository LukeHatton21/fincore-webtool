import xarray as xr
import pandas as pd
import numpy as np
import streamlit as st
import itertools

class WaccCalculator:
    def __init__(self, tech_premiums, penetration_boundaries, maturity_premiums, exchange_rates, inflation):
        """ Initialises the WACC Calculator Class, which is used to calculate an estimate of the cost of capital at
         a national level for countries with available data for a specific technology
        
        Inputs:
        tech_premiums: CSV containing mapping of relative tech premiums, measured compared to solar
        
        """
    
        # Read in relevant inputs
        self.tech_premiums = pd.read_csv(tech_premiums)
        self.penetration_boundaries = pd.read_csv(penetration_boundaries)
        self.maturity_premiums = pd.read_csv(maturity_premiums)
        self.exchange_rates = pd.read_csv(exchange_rates)
        self.inflation = pd.read_csv(inflation)

        # Set up initial assumptions
        self.lenders_margin = 2
        

    def calculate_country_wacc(self, rf_rate, crp, cds, tax_rate, technology, year, debt_share=None, erp=None, tech_penetration=None, market_maturity=None, country_code=None):
        

        # Calculate maturity of market and tech premium
        tech_maturity = self.calculate_maturity_tech_premium(technology, tech_penetration)
        technology_premium = tech_maturity.loc[tech_maturity["Country code"] != "ERP", "Tech_Premium"]

        # Calculate relative technology premium
        relative_premium = self.lookup_tech_premium(technology)
        if technology in ["Wind", "Wind Offshore", "Solar"]:
            technology_premium = technology_premium
        else:
            technology_premium = technology_premium + relative_premium

        # Extract country code
        if country_code is None:
            country_code = crp.loc[crp["Country code"] != "ERP", "Country code"]
        
        # Extract values
        if 'Country code' in crp.columns:
            crp = crp.loc[crp["Country code"] != "ERP", "CRP_"+str(year)]
            cds = cds.loc[cds["Country code"] != "ERP", "CDS_"+str(year)]
            tax_rate = tax_rate.loc[tax_rate["Country code"] != "ERP", "Tax_Rate"]
        

        
        # Calculate debt share, if applicable
        if debt_share is None:
            debt_share = self.calculate_debt_share(crp)


        # Calculate the cost of equity
        debt_cost = rf_rate + cds + self.lenders_margin + technology_premium

        # Calculate the cost of debt
        equity_cost = rf_rate + crp + erp + technology_premium

        # Calculate the weighted average cost of capital
        estimated_wacc = debt_cost * (debt_share/100) * (1 - (tax_rate/100)) + equity_cost * (1 - (debt_share/100))

        # Extract contributions to the overall WACC
        risk_free_contributions = rf_rate*((debt_share / 100 * (1 - tax_rate/100)) + (1 - debt_share / 100))
        crp_contributions = cds*(debt_share / 100 * (1 - tax_rate/100)) + crp*(1 - debt_share / 100)
        erp_contributions = erp * ( 1 - (debt_share / 100))
        lm_contributions = self.lenders_margin * (debt_share / 100) * (1-tax_rate/100)
        tech_premium_contributions = technology_premium*((debt_share / 100 * (1 - tax_rate/100)) + (1 - debt_share / 100))


        # Include in a pandas dataframe
        results_df = pd.DataFrame(data={"Country code": country_code, "Risk_Free":risk_free_contributions, "Country_Risk": crp_contributions, "Equity Risk": erp_contributions, "Lenders Margin": lm_contributions, 
                                        "Technology_Risk": tech_premium_contributions, "Equity_Cost": equity_cost, "Debt_Cost": debt_cost, "WACC": estimated_wacc, "Debt_Share": debt_share, "Tax_Rate": tax_rate, "Year":year})
        

        return results_df
    

    def calculate_maturity_tech_premium(self, technology, tech_penetration):

        # Extract boundaries for the given technology
        tech_boundaries = self.penetration_boundaries
        maturity_premiums = self.maturity_premiums
        
        # Check if technology has specific boundaries
        if tech_boundaries["TECH"].isin([technology]).any():
            tech_boundaries_selected = tech_boundaries.loc[tech_boundaries["TECH"]==technology]
            maturity_premium_selected = maturity_premiums.loc[maturity_premiums["TECH"]==technology]
        else:
            tech_boundaries_selected = tech_boundaries.loc[tech_boundaries["TECH"]=="Other"]
            maturity_premium_selected = maturity_premiums.loc[maturity_premiums["TECH"]=="Other"]

        # Establish the boundaries
        intermediate = tech_boundaries_selected["INTERMEDIATE"].values[0]
        mature = tech_boundaries_selected["MATURE"].values[0]

        # Establish the premiums
        maturity_premium = maturity_premium_selected["MATURE"].values[0]
        intermediate_premium = maturity_premium_selected["INTERMEDIATE"].values[0]
        immature_premium = maturity_premium_selected["IMMATURE"].values[0]
        

        # Calculate the maturity based on boundaries
        tech_penetration["Maturity"] = tech_penetration.apply(
            lambda row: "Mature" if row["Penetration"] > mature 
            else ("Intermediate"if row["Penetration"] > intermediate
                else "Immature"),
            axis=1
            ) 
        
        # Calculate the intermediate premium
        tech_penetration["Intermediate"]= (maturity_premium - immature_premium)/(mature - intermediate)*(tech_penetration["Penetration"]-intermediate) + immature_premium
        
        tech_penetration["Tech_Premium"] = tech_penetration.apply(
            lambda row: maturity_premium if row["Maturity"] == "Mature"
            else (row["Intermediate"] if row["Maturity"] == "Intermediate"
                else immature_premium),
            axis=1
            )
        tech_penetration = tech_penetration.drop(columns=["Intermediate"])

        return tech_penetration
    
    def calculate_debt_share(self, crp, max_crp=None):

        # Calculate debt share based on CRP, assuming it ranges in line with CRP data
        debt_share = 80 - 40 * (crp / np.nanmax(crp))

        return debt_share
    

    def calculate_debt_share_individual(self, crp):

        # Calculate debt share based on CRP, assuming it ranges in line with CRP data
        debt_share = 80 - 40 * (crp / 25)

        return debt_share

    def lookup_tech_premium(self, technology):

        # Extract relative tech premium
        tech_premiums = self.tech_premiums

        # Locate the value of the tech premium
        if tech_premiums["TECH"].isin([technology]).any():
            relative_premium = tech_premiums.loc[tech_premiums["TECH"]==technology]["PREMIUM"].values[0]
        else:
            relative_premium = tech_premiums.loc[tech_premiums["TECH"]=="Other"]["PREMIUM"].values[0]
        
        return relative_premium



    def calculate_wacc_individual(self, rf_rate, crp, cds, tax_rate, technology, year, country_code, tech_penetration, debt_share=None, erp=None, market_maturity=None, penetration_value=None):
        

        # Calculate maturity of market and tech premium
        if penetration_value is not None:
            tech_penetration = pd.DataFrame({"Country code": [country_code], "Penetration":penetration_value})
        tech_maturity = self.calculate_maturity_tech_premium(technology, tech_penetration)
        technology_premium = tech_maturity.loc[tech_maturity["Country code"] != "ERP", "Tech_Premium"]
            
        # Calculate relative technology premium
        relative_premium = self.lookup_tech_premium(technology)
        if technology in ["Wind", "Wind Offshore", "Solar"]:
            technology_premium = technology_premium
        else:
            technology_premium = technology_premium + relative_premium
        
        # Calculate debt share, if applicable
        if debt_share is None:
            debt_share = self.calculate_debt_share_individual(crp)

        # Calculate the cost of equity
        debt_cost = rf_rate + cds + self.lenders_margin + technology_premium

        # Calculate the cost of debt
        equity_cost = rf_rate + crp + erp + technology_premium

        # Calculate the weighted average cost of capital
        estimated_wacc = debt_cost * (debt_share/100) * (1 - (tax_rate/100)) + equity_cost * (1 - (debt_share/100))

        # Extract contributions to the overall WACC
        risk_free_contributions = rf_rate*((debt_share / 100 * (1 - tax_rate/100)) + (1 - debt_share / 100))
        crp_contributions = cds*(debt_share / 100 * (1 - tax_rate/100)) + crp*(1 - debt_share / 100)
        erp_contributions = erp * ( 1 - (debt_share / 100))
        lm_contributions = self.lenders_margin * (debt_share / 100) * (1-tax_rate/100)
        tech_premium_contributions = technology_premium*((debt_share / 100 * (1 - tax_rate/100)) + (1 - debt_share / 100))


        # Include in a pandas dataframe
        results_df = pd.DataFrame(data={"Country code": country_code, "Risk_Free":risk_free_contributions, "Country_Risk": crp_contributions, "Equity Risk": erp_contributions, "Lenders Margin": lm_contributions, 
                                        "Technology_Risk": tech_premium_contributions, "Equity_Cost": equity_cost, "Debt_Cost": debt_cost, "WACC": estimated_wacc, "Debt_Share": debt_share, "Tax_Rate": tax_rate, "Year":year,
                                        "CDS":cds, "CRP": erp, "ERP": erp, "Tech_Premium": technology_premium.values[0], "LM": self.lenders_margin})
        

        return results_df
    







    def tech_premium_individual(self, technology, tech_penetration, market_maturity=None):

        # Extract boundaries for the given technology
        tech_boundaries = self.penetration_boundaries
        maturity_premiums = self.maturity_premiums
        
        # Check if technology has specific boundaries
        if tech_boundaries["TECH"].isin([technology]).any():
            tech_boundaries_selected = tech_boundaries.loc[tech_boundaries["TECH"]==technology]
            maturity_premium_selected = maturity_premiums.loc[maturity_premiums["TECH"]==technology]
        else:
            tech_boundaries_selected = tech_boundaries.loc[tech_boundaries["TECH"]=="Other"]
            maturity_premium_selected = maturity_premiums.loc[maturity_premiums["TECH"]=="Other"]

        # Establish the boundaries
        intermediate = tech_boundaries_selected["INTERMEDIATE"].values[0]
        mature = tech_boundaries_selected["MATURE"].values[0]

        # Establish the premiums
        maturity_premium = maturity_premium_selected["MATURE"].values[0]
        intermediate_premium = maturity_premium_selected["INTERMEDIATE"].values[0]
        immature_premium = maturity_premium_selected["IMMATURE"].values[0]
        

        # Calculate the maturity based on boundaries
        if tech_penetration > mature:
            maturity = "Mature"
        elif tech_penetration > intermediate:
            maturity = "Intermediate"
        else:
            maturity = "Immature"

        # If maturity is specified, take that
        if market_maturity is not None:
            maturity = market_maturity

        # Calculate tech premiunm
        if maturity == "Mature":
            tech_premium = maturity_premium
        elif maturity == "Intermediate":
            tech_premium = (maturity_premium - immature_premium)/(mature - intermediate)*(tech_penetration-intermediate) + immature_premium
        else:
            tech_premium = immature_premium


        return tech_premium
    

    def convert_currencies_usd_to_local(self, value, country_code, year):

        # Extract inflation data
        inflation = self.inflation

        # Extract USD and local inflation
        USD_inflation = inflation.loc[inflation["Country code"] == "USA"]
        local_inflation = inflation.loc[inflation["Country code"] == country_code]

        # Cap year at 2025 for forward-looking data
        forward_year = min(int(year), 2025)
        historical_year = int(year)

        # ── Forward Inflation ──────────────────────────────────────────────────────

        # Calculate 5-year compounded forward USD inflation
        future_USD_inflation = USD_inflation[[str(forward_year), str(forward_year+1), str(forward_year+2), str(forward_year+3), str(forward_year+4)]]
        multipliers = ((100 + future_USD_inflation) / 100).prod(axis=1)
        USD_inflation_compound = multipliers ** (1 / 5) - 1

        # Calculate 5-year compounded forward local inflation
        future_local_inflation = local_inflation[[str(forward_year), str(forward_year+1), str(forward_year+2), str(forward_year+3), str(forward_year+4)]]
        multipliers = ((100 + future_local_inflation) / 100).prod(axis=1)
        local_inflation_compound = multipliers ** (1 / 5) - 1

        # ── Historical FX Depreciation ─────────────────────────────────────────────

        # Extract historical exchange rates (local per USD)
        local_exchange_rates = self.exchange_rates[[
            "Country code",
            "ER_" + str(historical_year - 4),
            "ER_" + str(historical_year - 3),
            "ER_" + str(historical_year - 2),
            "ER_" + str(historical_year - 1),
            "ER_" + str(historical_year)
        ]]
        local_exchange_rates = local_exchange_rates.loc[local_exchange_rates["Country code"] == country_code]

        # Raw FX depreciation over 5 years
        depreciation = local_exchange_rates["ER_" + str(historical_year)] / local_exchange_rates["ER_" + str(historical_year - 4)]

        # ── Historical Inflation ───────────────────────────────────────────────────

        # 5-year compounded historical USD inflation
        historic_USD_inflation = USD_inflation[[str(historical_year-4), str(historical_year-3), str(historical_year-2), str(historical_year-1), str(historical_year)]]
        multipliers = ((100 + historic_USD_inflation) / 100).prod(axis=1)
        USD_historic_inflation = multipliers ** (1 / 5) - 1

        # 5-year compounded historical local inflation
        historic_local_inflation = local_inflation[[str(historical_year-4), str(historical_year-3), str(historical_year-2), str(historical_year-1), str(historical_year)]]
        multipliers = ((100 + historic_local_inflation) / 100).prod(axis=1)
        local_historic_inflation = multipliers ** (1 / 5) - 1

        # ── Excess Depreciation ────────────────────────────────────────────────────

        # Isolate depreciation beyond what PPP would predict
        # PPP-implied move = (1 + local_inflation) / (1 + USD_inflation)
        ppp_implied = (1 + local_historic_inflation.values[0]) / (1 + USD_historic_inflation.values[0])
        expected_fx_depreciation = (depreciation.values[0] / ppp_implied) - 1

        # ── Convert USD Rate to Local ──────────────────────────────────────────────

        # Invert the inflation ratio and apply excess depreciation
        # USD → Local: higher local inflation increases local rate
        # Excess depreciation further increases local rate
        converted_value = (
            (1 + value)
            * (1 + local_inflation_compound.values[0])   # local inflation increases local rate
            / (1 + USD_inflation_compound.values[0])     # USD inflation decreases local rate
            * (1 + expected_fx_depreciation)             # structural FX weakness adds to local rate
        ) - 1

        return converted_value

    def convert_currencies_usd_to_local_df(
    self,
    df,
    value_col="Risk_Free",
    country_col="Country_code",
    year_col="year",
    output_col="Local_Risk_Free"
):
        """
        Converts USD-denominated rates in `value_col` to local currency rates row-by-row.

        Expected columns in df:
        - country_col (default: country_code)
        - year_col (default: year)
        - value_col (default: value)

        Returns:
        - copy of df with `output_col`
        """

        out = df.copy()

        def _convert_row(row):
            country_code = row[country_col]
            year = row[year_col]
            value = row[value_col]

            if pd.isna(country_code) or pd.isna(year) or pd.isna(value):
                return np.nan

            try:
                return self.convert_currencies_usd_to_local(
                    value=float(value),
                    country_code=str(country_code),
                    year=int(year)
                )
            except Exception:
                return np.nan

        out[output_col] = out.apply(_convert_row, axis=1)
        return out

    def convert_currencies_local_usd(self, value, country_code, year):

        # Extract inflation
        inflation = self.inflation
        
        # Extract expected inflation
        USD_inflation = inflation.loc[inflation["Country code"] == "USA"]
        local_inflation = inflation.loc[inflation["Country code"] == country_code]

        # Calculate five year forward rates for USD
        if int(year) > 2025:
            year = 2025
        else:
            year = int(year)
        future_USD_inflation = USD_inflation[[str(year), str(year+1), str(year+2), str(year+3), str(year+4)]]
        multipliers = ((100 + future_USD_inflation) / 100).prod(axis=1)
        USD_inflation_compound = (multipliers) ** (1 / 5) - 1

        # Calculate five year forward rate in local
        future_local_inflation = local_inflation[[str(year), str(year+1), str(year+2), str(year+3), str(year+4)]]
        multipliers = ((100 + future_local_inflation) / 100).prod(axis=1)
        local_inflation_compound = (multipliers) ** (1 / 5) - 1

        # Calculate expected fx depreciation
        local_exchange_rates = self.exchange_rates[["Country code", "ER_" + str(year-4), "ER_" + str(year-3), "ER_" + str(year-2), "ER_" + str(year-1), "ER_" + str(year)]]
        local_exchange_rates = local_exchange_rates.loc[local_exchange_rates["Country code"]==country_code]
        depreciation = local_exchange_rates["ER_"+str(year)] / local_exchange_rates["ER_"+str(year-4)]

        # Calculate historical USD inflations 
        historic_USD_inflation = USD_inflation[[str(year-4), str(year-3), str(year-2), str(year-1), str(year)]]
        multipliers = ((100 + historic_USD_inflation) / 100).prod(axis=1)
        USD_historic_inflation = (multipliers) ** (1 / 5) - 1

        # Calculate historical local inflation
        historic_local_inflation = local_inflation[[str(year-4), str(year-3), str(year-2), str(year-1), str(year)]]
        multipliers = ((100 + historic_local_inflation) / 100).prod(axis=1)
        local_historic_inflation = (multipliers) ** (1 / 5) - 1

        # Calculate additional depreciation
        expected_fx_depreciation = (depreciation / (1 + local_historic_inflation.values[0]) / (1 + USD_historic_inflation.values[0])) - 1

        # Convert between currencies
        converted_value = ((1 + value) * (1 + local_inflation_compound.values[0]) / (1 + USD_inflation_compound.values[0]) * (1 + expected_fx_depreciation.values[0]))  - 1

        return converted_value


    def estimate_currency_risk_premium(
    self,
    country_code,
    year,
    lookback=20,
    risk_aversion=0.1
):
        """
        Estimate a currency risk premium based on annual excess depreciation
        beyond what would be implied by relative inflation versus USD.

        Methodology
        -----------
        For each year n in the historical sample:

            C_inflation,n = ((1 + I_loc,n) / (1 + I_hard,n)) - 1
            C_dep,n       = (E_n - E_n-1) / E_n-1
            C_exc_dep,n   = C_dep,n - C_inflation,n

        The currency risk premium is then estimated as:

            mean(C_exc_dep) + risk_aversion * std(C_exc_dep)

        Parameters
        ----------
        country_code : str
            Country code of the local currency.
        year : int or str
            Final year in the estimation sample.
        lookback : int, default=20
            Number of annual excess depreciation observations to use.
            For example, if year=2025 and lookback=20, the method uses
            annual observations from 2006 to 2025, requiring exchange-rate
            data from 2005 to 2025.
        risk_aversion : float, default=0.5
            Stress multiplier applied to the standard deviation of excess depreciation.

        Returns
        -------
        dict
            Dictionary containing summary statistics and the annual excess
            depreciation series used in the estimation.
        """

        inflation = self.inflation
        exchange_rates = self.exchange_rates
        year = int(year)

        # Extract inflation rows
        hard_inflation = inflation.loc[inflation["Country code"] == "USA"]
        local_inflation = inflation.loc[inflation["Country code"] == country_code]

        if hard_inflation.empty:
            raise ValueError("No inflation data found for hard currency country code 'USA'")
        if local_inflation.empty:
            raise ValueError(f"No inflation data found for country code: {country_code}")

        # Extract exchange-rate row
        local_exchange_rates = exchange_rates.loc[
            exchange_rates["Country code"] == country_code
        ]

        if local_exchange_rates.empty:
            raise ValueError(f"No exchange-rate data found for country code: {country_code}")

        # Annual observations for n = year-lookback+1 to year
        observation_years = list(range(year - lookback + 1, year + 1))

        records = []

        for n in observation_years:
            inflation_col = str(n)
            er_prev_col = f"ER_{n-1}"
            er_curr_col = f"ER_{n}"

            # Validate required columns
            missing_inflation_cols = [
                col for col in [inflation_col] if col not in inflation.columns
            ]
            missing_er_cols = [
                col for col in [er_prev_col, er_curr_col] if col not in exchange_rates.columns
            ]

            if missing_inflation_cols:
                raise ValueError(f"Missing inflation column(s): {missing_inflation_cols}")
            if missing_er_cols:
                raise ValueError(f"Missing exchange-rate column(s): {missing_er_cols}")

            # Inflation values
            i_loc = local_inflation[inflation_col].values[0]
            i_hard = hard_inflation[inflation_col].values[0]

            if pd.isna(i_loc) or pd.isna(i_hard):
                raise ValueError(f"Missing inflation value(s) for year {n}")

            # Convert percentage inflation to decimal
            i_loc = i_loc / 100
            i_hard = i_hard / 100

            # Inflation-implied depreciation
            c_inflation = ((1 + i_loc) / (1 + i_hard)) - 1

            # Exchange-rate depreciation against USD
            e_prev = local_exchange_rates[er_prev_col].values[0]
            e_curr = local_exchange_rates[er_curr_col].values[0]

            if pd.isna(e_prev) or pd.isna(e_curr):
                raise ValueError(
                    f"Missing exchange-rate value(s) for {country_code} in years {n-1} or {n}"
                )

            c_dep = (e_curr - e_prev) / e_prev

            # Excess depreciation
            c_exc_dep = c_dep - c_inflation

            records.append({
                "year": n,
                "local_inflation": i_loc,
                "hard_inflation": i_hard,
                "inflation_implied_depreciation": c_inflation,
                "actual_depreciation": c_dep,
                "excess_depreciation": c_exc_dep
            })

        results = pd.DataFrame(records)

        mean_excess_depreciation = results["excess_depreciation"].mean()
        std_excess_depreciation = results["excess_depreciation"].std(ddof=1)

        currency_risk_premium = (risk_aversion * std_excess_depreciation
        )

        return {
            "country_code": country_code,
            "year": year,
            "lookback": lookback,
            "risk_aversion": risk_aversion,
            "mean_excess_depreciation": mean_excess_depreciation,
            "std_excess_depreciation": std_excess_depreciation,
            "currency_risk_premium": currency_risk_premium,
            "excess_depreciation_series": results
        }

   