import streamlit as st
import folium
import math
import pandas as pd
import numpy as np
from streamlit_folium import st_folium
import branca.colormap as cm
import altair as alt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from  streamlit_vertical_slider import vertical_slider 
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class VisualiserClass:
    def __init__(self, crp_data, tech_premium):
        """ Initialises the VisualiserClass, which is used to generate plots for the webtool """

        # Read in Data
        self.crp_data = crp_data
        self.tech_premium = tech_premium


        # Get country name and country code dictionary
        self.crp_country = self.crp_data[["Country", "Country code"]]
        self.crp_country = self.crp_country.loc[self.crp_country["Country code"] != "ERP"]
        self.crp_dictionary = pd.Series(self.crp_country["Country code"].values,index=self.crp_country["Country"]).to_dict()
        self.crp_dict_reverse = self.inverse_dict(self.crp_dictionary)

        # Get tech name and coding dictionary
        self.techs = self.tech_premium[["NAME", "TECH"]]
        self.techs = self.techs.loc[self.techs["TECH"] != "OTHER"]
        self.tech_dictionary = pd.Series(self.techs["TECH"].values,index=self.techs["NAME"]).to_dict()
        self.tech_dict_reverse = self.inverse_dict(self.tech_dictionary)

    def inverse_dict(self, dictionary):
        inv_dict = {v: k for k, v in dictionary.items()}
        return inv_dict

    def select_finance_metric(self):

        instrument = st.selectbox(
            "Instrument",
            options=["CoD", "CoE"],
            index=0
        )

        source = st.selectbox(
            "Source of finance",
            options=[
                "International Commercial",
                "International Public",
                "Domestic Commercial",
                "Domestic Public",
                "Grant"
            ],
            index=0
        )

        selected_col = f"{instrument}_{source.replace(' ', '_')}"
        label = f"{instrument} - {source}"

        return instrument, source, selected_col, label
    
    def display_finance_map(self, df, value_col, value_label):
        def _safe_scalar(df_indexed, iso3, col, agg="mean"):
            if iso3 not in df_indexed.index or col not in df_indexed.columns:
                return None
            v = df_indexed.loc[iso3, col]
            # If duplicate index -> Series
            if isinstance(v, pd.Series):
                v = pd.to_numeric(v, errors="coerce")
                if agg == "first":
                    v = v.dropna().iloc[0] if not v.dropna().empty else np.nan
                else:
                    v = v.mean()
            else:
                v = pd.to_numeric(v, errors="coerce")
            return None if pd.isna(v) else float(v)
        map_obj = folium.Map(
            location=[10, 0],
            zoom_start=1,
            control_scale=True,
            scrollWheelZoom=True,
            tiles="CartoDB positron"
        )

        map_df = df.copy()
        map_df = map_df.rename(columns={"Country code": "iso3_code"})

        # keep required cols if present
        keep_cols = ["iso3_code", value_col, "Tax_Rate"]
        keep_cols = [c for c in keep_cols if c in map_df.columns]
        map_df = map_df[keep_cols]

        choropleth = folium.Choropleth(
            geo_data="./DATA/country_boundaries.geojson",
            data=map_df,
            columns=("iso3_code", value_col),
            key_on="feature.properties.iso3_code",
            line_opacity=0.8,
            highlight=True,
            fill_color="YlGnBu",
            nan_fill_color="grey",
            legend_name=f"{value_label} (%)",
        )
        choropleth.geojson.add_to(map_obj)

        df_indexed = map_df.set_index("iso3_code")

        for feature in choropleth.geojson.data["features"]:
            iso3 = feature["properties"]["iso3_code"]

            val = _safe_scalar(df_indexed, iso3, value_col, agg="mean")
            tax = _safe_scalar(df_indexed, iso3, "Tax_Rate", agg="mean")

            feature["properties"][value_label] = f"{val:.2f}%" if val is not None else "N/A"
            feature["properties"]["Tax_Rate"] = f"{tax:.2f}%" if tax is not None else "N/A"

        choropleth.geojson.add_child(
            folium.features.GeoJsonTooltip(
                fields=["english_short", value_label, "Tax_Rate"],
                aliases=["Country:", f"{value_label}:", "Tax Rate:"],
                localize=True,
                style="""
                    background-color: #F0EFEF;
                    border: 2px solid black;
                    border-radius: 3px;
                    box-shadow: 3px;
                """,
                max_width=400,
            )
        )

        st_map = st_folium(map_obj, width=900, height=420)

        country_name = ""
        if st_map and st_map.get("last_active_drawing"):
            country_name = st_map["last_active_drawing"]["properties"].get("english_short", "")

        return country_name


    @st.cache_data
    def get_sorted_waccs(self, df, technology):

        if technology == "Solar PV":
            column = "solar_pv_wacc"
        elif technology == "Onshore Wind":
            column = "onshore_wacc"
        elif technology == "Offshore Wind":
            column = "offshore_waccs"

        sorted_df = df.sort_values(by=column, axis=0, ascending=True)
        list = ["solar_pv_wacc", "onshore_wacc", "offshore_wacc"]
        for columns in list:
            if columns == column:
                list.remove(columns)
        sorted_df = sorted_df.drop(labels=list, axis="columns")
        sorted_df = sorted_df.dropna(subset=column)
        sorted_df = sorted_df.rename(columns={column:"WACC"})
        sorted_df["WACC"] = sorted_df["WACC"].round(decimals=2)

        return sorted_df

    def sort_waccs(self, df):

        sorted_df = df.sort_values(by="WACC", axis=0, ascending=True)
        list = ["WACC", "Equity_Cost", "Debt_Cost", "Debt_Share", "Tax_Rate"]
        sorted_df = sorted_df.drop(labels=list, axis="columns")
        
        return sorted_df

    def financing_inputs_sidebar(self):
        sources = [
        "International Commercial",
        "International Public",
        "Domestic Commercial",
        "Domestic Public",
        "Grant"
    ]

        # ---------- defaults ----------
        default_share = {s: 20.0 for s in sources}
        default_debt = {
            "International Commercial": 70.0,
            "International Public": 50.0,
            "Domestic Commercial": 65.0,
            "Domestic Public": 45.0,
            "Grant": 0.0
        }

        if "source_share_state" not in st.session_state:
            st.session_state.source_share_state = default_share.copy()
        if "debt_share_state" not in st.session_state:
            st.session_state.debt_share_state = default_debt.copy()

        st.sidebar.markdown("## Financing Inputs")
        st.sidebar.caption("Set overall source shares and debt share per source.")

        # ---------- actions FIRST (before widgets) ----------
        total_share_pre = sum(st.session_state.source_share_state.values())

        a, b = st.sidebar.columns(2)
        normalize_clicked = a.button("Normalize to 100%", use_container_width=True)
        reset_clicked = b.button("Reset defaults", use_container_width=True)

        if reset_clicked:
            st.session_state.source_share_state = default_share.copy()
            st.session_state.debt_share_state = default_debt.copy()
            st.rerun()

        if normalize_clicked and total_share_pre > 0:
            st.session_state.source_share_state = {
                s: (v * 100.0 / total_share_pre)
                for s, v in st.session_state.source_share_state.items()
            }
            st.rerun()

        # ---------- widgets ----------
        for s in sources:
            c1, c2 = st.sidebar.columns([1.7, 1.9])

            with c1:
                val = st.number_input(
                    f"{s} share (%)",
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    value=float(st.session_state.source_share_state[s]),
                    key=f"num_share_{s}"
                )
                st.session_state.source_share_state[s] = float(val)

            with c2:
                if s == "Grant":
                    st.write("No debt")
                    st.session_state.debt_share_state[s] = 0.0
                else:
                    dval = st.slider(
                        f"{s} debt share (%)",
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        value=float(st.session_state.debt_share_state[s]),
                        key=f"sld_debt_{s}"
                    )
                    st.session_state.debt_share_state[s] = float(dval)

        # ---------- validation ----------
        total_share = sum(st.session_state.source_share_state.values())
        st.sidebar.markdown(f"**Total source share:** {total_share:.1f}%")
        if abs(total_share - 100.0) > 1e-9:
            st.sidebar.warning("Shares do not sum to 100%. Click 'Normalize to 100%'.")

        # ---------- output ----------
        shares_df = pd.DataFrame({
            "source": sources,
            "Share": [st.session_state.source_share_state[s] for s in sources],
            "Debt_Share": [st.session_state.debt_share_state[s] for s in sources]
        })

        shares_df["Equity_Share"] = 100.0 - shares_df["Debt_Share"]
        shares_df["Debt_Contribution"] = shares_df["Share"] * shares_df["Debt_Share"] / 100.0
        shares_df["Equity_Contribution"] = shares_df["Share"] * shares_df["Equity_Share"] / 100.0

        return shares_df

    def plot_comparison_chart(self, df):
    # Melt dataframe
        df = df.rename(columns={"Risk_Free":" Risk Free", "Country_Risk":"Country Risk", "Technology_Risk":"Technology Risk"})
        data_melted = df.melt(id_vars="Year", var_name="Factor", value_name="Value")

        # Set order
        category_order = [' Risk Free', 'Country Risk', 'Equity Risk', 'Lenders Margin', 'Technology Risk']

        # Create chart
        chart = alt.Chart(data_melted).mark_bar().encode(
            x=alt.X('sum(Value):Q', stack='zero', title='Weighted Average Cost of Capital (%)'),
            y=alt.Y('Year:O', title='Country'),  # Sort countries by total value descending
            color=alt.Color('Factor:N', title='Factor'),
            order=alt.Order('Factor:O', sort="ascending"),  # Color bars by category
    ).properties(width=700)
        st.write(chart)


    def create_chloropleth_map(self, wacc_coverage):

        fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=['IEA Cost of Capital Observatory', 'Calcaterra et al. 2025',"Steffen 2020", 'This Work'],
        specs=[[{'type': 'choropleth'}, {'type': 'choropleth'}],
               [{'type': 'choropleth'}, {'type': 'choropleth'}]],
        vertical_spacing=0.03,
        horizontal_spacing=0.03
    )

        color_scales = {
            'FINCORE': 'Blues',
            'IEA': 'Reds',
            'STEFFEN': 'greys',
            'IRENA':'Greens',
        }

        for i, col in enumerate(['IEA', 'IRENA','STEFFEN','FINCORE']):
            fig.add_trace(
                go.Choropleth(
                    locations=wacc_coverage['Country code'],
                    z=wacc_coverage[col],
                    colorscale=color_scales[col],
                    zmin=wacc_coverage[col].min(),
                    zmax=wacc_coverage[col].max(),
                    colorbar_title=col,
                    locationmode='ISO-3',
                    showscale=False,
                ),
                row=(i//2) + 1, col=(i%2) + 1
            )
            fig.update_geos(
            row=(i//2) + 1, col=(i%2) + 1,
            projection_type='robinson',
            lataxis=dict(range=[-60, 85]),  # Set latitude bounds
            lonaxis=dict(range=[-180, 180])
            )
            fig.write_image(f"GlobalCoverage" + str(col) + ".png") # Set longitude bounds (full range))
        fig.update_layout(
        margin=dict(t=30, b=10, l=10, r=10),
        height=600,
        width=600
        )
        for annotation in fig['layout']['annotations']:
            annotation['y'] -= 0.01  # Adjusted for vertical stacking)

        

        fig.show()

        fig.write_image("GlobalCoverage.png")


    def vertical_sliders(self):

        col1, col2, col3, col4, col5 = st.columns(5)
        default_value = 20
        max_value = 100

        with col1:
            commercial_int = vertical_slider(
            label = "International Commercial",  #Optional
            key = "vert_01" ,
            height = 300, #Optional - Defaults to 300
            thumb_shape = "square", #Optional - Defaults to "circle"
            step = 1, #Optional - Defaults to 1
            default_value=100 ,#Optional - Defaults to 0
            min_value= 0, # Defaults to 0
            max_value= max_value , # Defaults to 10
            track_color = "blue", #Optional - Defaults to Streamlit Red
            slider_color = ('red','blue'), #Optional
            thumb_color= "orange", #Optional - Defaults to Streamlit Red
            value_always_visible = True ,#Optional - Defaults to False
            )
        with col2:
            public_int= vertical_slider(
            label = "International Public",  #Optional
            key = "vert_02" ,
            height = 300, #Optional - Defaults to 300
            thumb_shape = "square", #Optional - Defaults to "circle"
            step = 1, #Optional - Defaults to 1
            default_value=default_value ,#Optional - Defaults to 0
            min_value= 0, # Defaults to 0
            max_value= max_value , # Defaults to 10
            track_color = "blue", #Optional - Defaults to Streamlit Red
            slider_color = ('red','blue'), #Optional
            thumb_color= "orange", #Optional - Defaults to Streamlit Red
            value_always_visible = True ,#Optional - Defaults to False
            )
        with col3:
            commercial_dom = vertical_slider(
            label = "Domestic Commercial",  #Optional
            key = "vert_03" ,
            height = 300, #Optional - Defaults to 300
            thumb_shape = "square", #Optional - Defaults to "circle"
            step = 1, #Optional - Defaults to 1
            default_value=default_value ,#Optional - Defaults to 0
            min_value= 0, # Defaults to 0
            max_value= max_value , # Defaults to 10
            track_color = "blue", #Optional - Defaults to Streamlit Red
            slider_color = ('red','blue'), #Optional
            thumb_color= "orange", #Optional - Defaults to Streamlit Red
            value_always_visible = True ,#Optional - Defaults to False
            )
        with col4:
            public_dom = vertical_slider(
            label = "Domestic Public",  #Optional
            key = "vert_04" ,
            height = 300, #Optional - Defaults to 300
            thumb_shape = "square", #Optional - Defaults to "circle"
            step = 1, #Optional - Defaults to 1
            default_value=default_value ,#Optional - Defaults to 0
            min_value= 0, # Defaults to 0
            max_value= max_value , # Defaults to 10
            track_color = "blue", #Optional - Defaults to Streamlit Red
            slider_color = ('red','blue'), #Optional
            thumb_color= "orange", #Optional - Defaults to Streamlit Red
            value_always_visible = True ,#Optional - Defaults to False
            )
        with col5:
            grants = vertical_slider(
            label = "Grants",  #Optional
            key = "vert_05" ,
            height = 300, #Optional - Defaults to 300
            thumb_shape = "square", #Optional - Defaults to "circle"
            step = 1, #Optional - Defaults to 1
            default_value=default_value ,#Optional - Defaults to 0
            min_value= 0, # Defaults to 0
            max_value= max_value , # Defaults to 10
            track_color = "blue", #Optional - Defaults to Streamlit Red
            slider_color = ('red','blue'), #Optional
            thumb_color= "orange", #Optional - Defaults to Streamlit Red
            value_always_visible = True ,#Optional - Defaults to False
            )
        shares_df = pd.DataFrame(data={"source": ["International Commercial", "International Public", 
                                            "Domestic Commercial", "Domestic Public", "Grant"], 
                                 "Share": [commercial_int, public_int, commercial_dom, public_dom, grants]})

        return shares_df

    def show_source_average(self, df, overall):
        
        def round_up_to_nearest_5(n):
            return math.ceil(n / 5) * 5

        # Fix for the case where shares exceed 100
        df["Share"] = df["Share"] * 100 / df["Share"].sum()
        
        # Calculate the cumulative share
        df["cumulative_share"] = df["Share"].cumsum()
        df["Cost_of_Capital"].loc[df["Cost_of_Capital"]==0] = 0.1
        # Create figure
        fig = make_subplots(rows=1, cols=2, column_widths=[0.85, 0.15])
        
        # Produce stepped chart with contributions
        for index, row in df.iterrows():
            fig.add_trace(go.Bar(
            name=row["source"],
            y=[row["Cost_of_Capital"]],
            x=[row["cumulative_share"]-row["Share"]],
            width=[row["Share"]],
            offset=0),
            row=1, 
            col=1)
        # Produce overall cost of capital
        fig.add_trace(go.Bar(
            name="Overall cost of capital",
            y=[overall],
            x=[0],
            width=[10],
            offset=0),
            row=1, 
            col=2)
        # Add in axis
        fig.update_xaxes(title_text="Share of total financing (%)", row=1, col=1)
        fig.update_xaxes(title_text="Overall cost of capital", row=1, col=2)
        fig.update_yaxes(title_text="Cost of capital (%)", row=1, col=1, range=[0, round_up_to_nearest_5(df["Cost_of_Capital"].max())])
        fig.update_yaxes(row=1, col=2, range=[0, round_up_to_nearest_5(df["Cost_of_Capital"].max())])
        
        # Produce plotly chart
        st.plotly_chart(fig)

    def plot_comparison_chart(self, df):
        # Melt dataframe
        df = df.rename(columns={"Risk_Free":" Risk Free", "Country_Risk":"Country Risk", "Technology_Risk":"Technology Risk"})
        data_melted = df.melt(id_vars="Year", var_name="Factor", value_name="Value")

        # Set order
        category_order = [' Risk Free', 'Country Risk', 'Equity Risk', 'Lenders Margin', 'Technology Risk']

        # Create chart
        chart = alt.Chart(data_melted).mark_bar().encode(
            x=alt.X('sum(Value):Q', stack='zero', title='Weighted Average Cost of Capital (%)'),
            y=alt.Y('Year:O', title='Country'),  # Sort countries by total value descending
            color=alt.Color('Factor:N', title='Factor'),
            order=alt.Order('Factor:O', sort="ascending"),  # Color bars by category
    ).properties(width=700)
        st.write(chart)

    def plot_ranking_table_tech(self, raw_df, tech_codes):

        # Select techs
        df = raw_df[raw_df["Technology"].isin(tech_codes)]
        df["Technology"].replace(self.tech_dict_reverse, inplace=True)

        # Drop year
        new_df = df.drop(columns=["Year", "Country code"])

        # Melt dataframe
        new_df = new_df.rename(columns={"Risk_Free":" Risk Free", "Country_Risk":"Country Risk", "Technology_Risk":"Technology Risk"})
        data_melted = new_df.melt(id_vars="Technology", var_name="Factor", value_name="Value")

        # Set order
        category_order = [' Risk Free', 'Country Risk', 'Equity Risk', 'Lenders Margin', 'Technology Risk']

        # Create chart
        chart = alt.Chart(data_melted).mark_bar().encode(
            x=alt.X('sum(Value):Q', stack='zero', title='Weighted Average Cost of Capital (%)'),
            y=alt.Y('Technology:O', sort="x", title='Technology'),  # Sort technologies by total value descending
            color=alt.Color('Factor:N', title='Factor').legend(orient="right", columns=3),
            order=alt.Order('Factor:O', sort="ascending"),  # Color bars by category
    ).properties(width=700)

        # Add x-axis to the top
        x_axis_top = chart.encode(
            x=alt.X('sum(Value):Q', stack='zero', title='Weighted Average Cost of Capital (%)', axis=alt.Axis(orient='top'))
        )

        # Combine the original chart and the one with the top axis
        chart_with_double_x_axis = alt.layer(
            chart,
            x_axis_top
        )



        st.write(chart_with_double_x_axis)

    def plot_cost_components_breakdown(self, breakdown):
        # Ensure numeric values for plotting and normalize column names
        breakdown = breakdown.copy()
        breakdown = breakdown.drop(columns=['country code', 'Country code'], errors='ignore')
        breakdown = breakdown.apply(pd.to_numeric, errors='coerce')

        # Filter debt and equity
        debt_df = breakdown[breakdown.index.str.startswith("Debt -")]
        equity_df = breakdown[breakdown.index.str.startswith("Equity -")]

        # Define color map for components
        color_map = {
            'Risk Free Rate': 'blue',
            'Country Risk': 'green',
            'Immaturity Premium': 'cyan',
            'Concessionality': 'magenta',
            'Country Default Spread': 'red',
            'Equity Risk Premium': 'orange',
            'Technology Risk Premium': 'purple',
            'Maturity Premium': 'brown',
            "Merchant Risk": 'pink',
            "Currency Risk Premium": 'gray',
        }

        def format_label(label):
            label = label.replace("International Commercial", "International<br>Commercial")
            label = label.replace("Domestic Commercial", "Domestic<br>Commercial")
            label = label.replace("International Public", "International<br>Public")
            label = label.replace("Domestic Public", "Domestic<br>Public")
            if "<br>" not in label and " " in label:
                parts = label.split(" ")
                mid = len(parts) // 2
                label = "<br>".join([" ".join(parts[:mid]), " ".join(parts[mid:])])
            return label

        # Create subplots
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Debt Cost Components", "Equity Cost Components"))

        shown_legends = set()

        # For debt
        debt_df.drop(columns=["Country Code"], inplace=True, errors='ignore')
        for idx in debt_df.index:
            row = debt_df.loc[idx]
            components = row.dropna()
            pos_base = 0
            neg_base = 0
            for comp in components.index:
                comp_value = components[comp]
                if pd.isna(comp_value):
                    continue
                if comp_value >= 0:
                    base = pos_base
                    pos_base += comp_value
                else:
                    base = neg_base
                    neg_base += comp_value
                show_legend = comp not in shown_legends
                if show_legend:
                    shown_legends.add(comp)
                fig.add_trace(go.Bar(
                    x=[format_label(idx.replace("Debt - ", ""))],
                    y=[comp_value],
                    name=comp,
                    marker_color=color_map.get(comp, 'gray'),
                    offsetgroup=0,
                    base=base,
                    customdata=[comp_value],
                    showlegend=show_legend,
                    hovertemplate="<b>%{fullData.name}</b><br>Height: %{customdata:.2f}<extra></extra>"
                ), row=1, col=1)

        # For equity
        equity_df.drop(columns=["Country Code"], inplace=True, errors='ignore')
        for idx in equity_df.index:
            row = equity_df.loc[idx]
            components = row.dropna()
            pos_base = 0
            neg_base = 0
            for comp in components.index:
                comp_value = components[comp]
                if pd.isna(comp_value):
                    continue
                if comp_value >= 0:
                    base = pos_base
                    pos_base += comp_value
                else:
                    base = neg_base
                    neg_base += comp_value
                show_legend = comp not in shown_legends
                if show_legend:
                    shown_legends.add(comp)
                fig.add_trace(go.Bar(
                    x=[format_label(idx.replace("Equity - ", ""))],
                    y=[comp_value],
                    name=comp,
                    marker_color=color_map.get(comp, 'gray'),
                    offsetgroup=1,
                    base=base,
                    customdata=[comp_value],
                    showlegend=show_legend,
                    hovertemplate="<b>%{fullData.name}</b><br>Height: %{customdata:.2f}<extra></extra>"
                ), row=1, col=2)

        # Calculate global min and max for aligned y-axes
        all_values = []
        for df in [debt_df, equity_df]:
            for idx in df.index:
                row = df.loc[idx]
                components = row.dropna()
                pos_base = 0
                neg_base = 0
                for comp_value in components.values:
                    if pd.isna(comp_value):
                        continue
                    if comp_value >= 0:
                        all_values.append(pos_base + comp_value)
                        pos_base += comp_value
                    else:
                        all_values.append(neg_base + comp_value)
                        neg_base += comp_value
                all_values.append(pos_base)
                all_values.append(neg_base)
        
        if all_values:
            global_min = min(all_values)
            global_max = max(all_values)
            # Add some padding
            padding = (global_max - global_min) * 0.1
            y_min = global_min - padding
            y_max = global_max + padding
        else:
            y_min = None
            y_max = None

        fig.update_layout(
            barmode='stack',
            title_text="Cost Components Breakdown",
            xaxis=dict(tickangle=0, automargin=True),
            xaxis2=dict(tickangle=0, automargin=True),
            legend=dict(
                orientation='h',
                x=0.5,
                y=-0.5,
                xanchor='center',
                yanchor='bottom',
                traceorder='normal',
            ),
            margin=dict(t=80)
        )
        
        # Update both y-axes to have the same range
        fig.update_yaxes(range=[y_min, y_max], row=1, col=1)
        fig.update_yaxes(range=[y_min, y_max], row=1, col=2)
        
        st.plotly_chart(fig)

    def plot_ranking_table(self, raw_df, country_codes):

        # Select countries
        df = raw_df[raw_df["Country code"].isin(country_codes)]

        # Drop year
        df = df.drop(labels="Year", axis="columns")

        # Melt dataframe
        df = df.rename(columns={"Risk_Free":" Risk Free", "Country_Risk":"Country Risk", "Technology_Risk":"Technology Risk"})
        data_melted = df.melt(id_vars="Country code", var_name="Factor", value_name="Value")

        # Set order
        category_order = [' Risk Free', 'Country Risk', 'Equity Risk', 'Lenders Margin', 'Technology Risk']

        # Create chart
        chart = alt.Chart(data_melted).mark_bar().encode(
            x=alt.X('sum(Value):Q', stack='zero', title='Weighted Average Cost of Capital (%)'),
            y=alt.Y('Country code:O', sort="x", title='Country'),  # Sort countries by total value descending
            color=alt.Color('Factor:N', title='Factor'),
            order=alt.Order('Factor:O', sort="ascending"),  # Color bars by category
    ).properties(width=700)

        # Add x-axis to the top
        x_axis_top = chart.encode(
            x=alt.X('sum(Value):Q', stack='zero', title='Weighted Average Cost of Capital (%)', axis=alt.Axis(orient='top'))
        )

        # Combine the original chart and the one with the top axis
        chart_with_double_x_axis = alt.layer(
            chart,
            x_axis_top
        )

        st.write(chart_with_double_x_axis)

    def plot_cost_components_from_underlying(
    self,
    underlying_data,
    concessionality,
    currency_risk=False,
    merchant_risk=False,
    currency_risk_col="Currency_Risk_Premium"
):

        if underlying_data is None or underlying_data.empty:
            st.warning("No underlying data available for breakdown plot.")
            return

        # Use first row (single scenario expected)
        row = underlying_data.iloc[0]

        # ---- Parameters (same as calculate_cost_of_capital) ----
        equity_weighting = 1.35
        merchant_risk_value = 2.0 if merchant_risk else 0.0
        merchant_risk_weighting = 1.5
        conc = 0.0 if concessionality == "Commercial Rate" else float(concessionality)
        local_country_passthrough = 0.75
        int_country_passthrough = 0.51

        # ---- Base terms ----
        riskfree_g = float(pd.to_numeric(row.get("Risk_Free", 0.0), errors="coerce"))
        riskfree_l = float(pd.to_numeric(row.get("Local_Risk_Free", riskfree_g), errors="coerce"))
        cds = float(pd.to_numeric(row.get("CDS", 0.0), errors="coerce"))
        erp = float(pd.to_numeric(row.get("ERP", 0.0), errors="coerce"))

        # Handle your naming variants safely
        tp = row.get("Technology_Premium", row.get("Tech_Premium", 0.0))
        tp = float(pd.to_numeric(tp, errors="coerce"))
        lm = float(pd.to_numeric(row.get("Lenders_Margin", row.get("Lenders Margin", 0.0)), errors="coerce"))

        if currency_risk and (currency_risk_col in underlying_data.columns):
            crfx = float(pd.to_numeric(row.get(currency_risk_col, 0.0), errors="coerce"))
        else:
            crfx = 0.0

        # ---- Build component dicts ----
        debt_components = {
            "International Commercial": {
                "Risk Free Rate": riskfree_g,
                "Country Default Spread": int_country_passthrough * cds,
                "Technology Risk Premium": tp,
                "Merchant Risk": merchant_risk_value,
                "Currency Risk Premium": crfx,
            },
            "International Public": {
                "Risk Free Rate": riskfree_g,
                "Country Default Spread": int_country_passthrough * cds,
                "Technology Risk Premium": tp,
                "Concessionality": -conc,
                "Merchant Risk": merchant_risk_value,
                "Currency Risk Premium": crfx,
            },
            "Domestic Commercial": {
                "Risk Free Rate": riskfree_l,
                "Country Default Spread": local_country_passthrough * cds,
                "Technology Risk Premium": tp,
                "Immaturity Premium": lm,
                "Merchant Risk": merchant_risk_value,
            },
            "Domestic Public": {
                "Risk Free Rate": riskfree_g,
                "Country Default Spread": cds,
            },
            "Grant": {}
        }

        equity_components = {
            "International Commercial": {
                "Risk Free Rate": riskfree_g,
                "Equity Risk Premium": erp,
                "Country Default Spread": int_country_passthrough * cds * equity_weighting,
                "Technology Risk Premium": tp,
                "Merchant Risk": merchant_risk_value * merchant_risk_weighting,
                "Currency Risk Premium": crfx,
            },
            "International Public": {
                "Risk Free Rate": riskfree_g,
                "Equity Risk Premium": erp,
                "Country Default Spread": int_country_passthrough * cds * equity_weighting,
                "Technology Risk Premium": tp,
                "Concessionality": -conc,
                "Merchant Risk": merchant_risk_value * merchant_risk_weighting,
                "Currency Risk Premium": crfx,
            },
            "Domestic Commercial": {
                "Risk Free Rate": riskfree_l,
                "Equity Risk Premium": erp,
                "Country Default Spread": local_country_passthrough * cds * equity_weighting,
                "Technology Risk Premium": tp,
                "Immaturity Premium": lm,
                "Merchant Risk": merchant_risk_value * merchant_risk_weighting,
            },
            "Domestic Public": {
                "Risk Free Rate": riskfree_g,
                "Country Default Spread": cds * equity_weighting,
            },
            "Grant": {}
        }

        # ---- Colors ----
        color_map = {
            "Risk Free Rate": "blue",
            "Country Risk": "green",
            "Immaturity Premium": "crimson",
            "Concessionality": "magenta",
            "Country Default Spread": "red",
            "Equity Risk Premium": "orange",
            "Technology Risk Premium": "purple",
            "Maturity Premium": "brown",
            "Merchant Risk": "pink",
            "Currency Risk Premium": "gray",
        }

        def format_label(label):
            label = label.replace("International Commercial", "International<br>Commercial")
            label = label.replace("Domestic Commercial", "Domestic<br>Commercial")
            label = label.replace("International Public", "International<br>Public")
            label = label.replace("Domestic Public", "Domestic<br>Public")
            if "<br>" not in label and " " in label:
                parts = label.split(" ")
                mid = len(parts) // 2
                label = "<br>".join([" ".join(parts[:mid]), " ".join(parts[mid:])])
            return label

        # ---- Plot ----
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Debt Cost Components", "Equity Cost Components"))
        shown_legends = set()

        # ---- debt stacked bars ----
        debt_x = []
        debt_totals = []
        for src, comps in debt_components.items():
            debt_x.append(format_label(src))
            vals = [v for v in comps.values() if not pd.isna(v)]
            debt_totals.append(sum(vals) if vals else 0.0)

            pos_base, neg_base = 0.0, 0.0
            for comp, val in comps.items():
                if pd.isna(val):
                    continue
                base = pos_base if val >= 0 else neg_base
                if val >= 0:
                    pos_base += val
                else:
                    neg_base += val

                show_legend = comp not in shown_legends
                if show_legend:
                    shown_legends.add(comp)

                fig.add_trace(
                    go.Bar(
                        x=[format_label(src)],
                        y=[val],
                        base=base,
                        name=comp,
                        marker_color=color_map.get(comp, "gray"),
                        showlegend=show_legend,
                        customdata=[val],
                        hovertemplate="<b>%{fullData.name}</b><br>Component: %{customdata:.2f}%<extra></extra>",
                    ),
                    row=1, col=1
                )

        # ---- debt total markers (hoverable) ----
        fig.add_trace(
            go.Scatter(
                x=debt_x,
                y=debt_totals,
                mode="markers",
                name="Total Cost of Debt",
                marker=dict(symbol="diamond", size=10, color="lightblue"),
                customdata=debt_totals,
                hovertemplate="<b>Total Cost of Debt</b><br>%{x}<br>Total: %{customdata:.2f}%<extra></extra>",
            ),
            row=1, col=1
        )

        # ---- equity stacked bars ----
        equity_x = []
        equity_totals = []
        for src, comps in equity_components.items():
            equity_x.append(format_label(src))
            vals = [v for v in comps.values() if not pd.isna(v)]
            equity_totals.append(sum(vals) if vals else 0.0)

            pos_base, neg_base = 0.0, 0.0
            for comp, val in comps.items():
                if pd.isna(val):
                    continue
                base = pos_base if val >= 0 else neg_base
                if val >= 0:
                    pos_base += val
                else:
                    neg_base += val

                show_legend = comp not in shown_legends
                if show_legend:
                    shown_legends.add(comp)

                fig.add_trace(
                    go.Bar(
                        x=[format_label(src)],
                        y=[val],
                        base=base,
                        name=comp,
                        marker_color=color_map.get(comp, "gray"),
                        showlegend=show_legend,
                        customdata=[val],
                        hovertemplate="<b>%{fullData.name}</b><br>Component: %{customdata:.2f}%<extra></extra>",
                    ),
                    row=1, col=2
                )

        # ---- equity total markers (hoverable) ----
        fig.add_trace(
            go.Scatter(
                x=equity_x,
                y=equity_totals,
                mode="markers",
                name="Total Cost of Equity",
                marker=dict(symbol="diamond", size=10, color="lightblue"),
                customdata=equity_totals,
                hovertemplate="<b>Total Cost of Equity</b><br>%{x}<br>Total: %{customdata:.2f}%<extra></extra>",
            ),
            row=1, col=2
        )

        # shared y range
        all_totals = debt_totals + equity_totals
        if all_totals:
            y_min = min(min(all_totals), 0)
            y_max = max(all_totals)
            pad = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
            y_range = [y_min - pad, y_max + pad]
            fig.update_yaxes(range=y_range, row=1, col=1)
            fig.update_yaxes(range=y_range, row=1, col=2)

        fig.update_layout(
            barmode="stack",
            title_text="Cost Components Breakdown",
            xaxis=dict(tickangle=0, automargin=True),
            xaxis2=dict(tickangle=0, automargin=True),
            legend=dict(
                orientation="h",
                x=0.5,
                y=-0.5,
                xanchor="center",
                yanchor="bottom",
                traceorder="normal",
            ),
            margin=dict(t=80),
        )

        st.plotly_chart(fig, use_container_width=True)
