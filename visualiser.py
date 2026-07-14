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
    
    def display_map(self, df, technology):
        map = folium.Map(location=[10, 0], zoom_start=1, control_scale=True, scrollWheelZoom=True, tiles='CartoDB positron')
        df = df.rename(columns={"Country code":"iso3_code"})

        choropleth = folium.Choropleth(
            geo_data='./DATA/country_boundaries.geojson',
            data=df,
            columns=('iso3_code', "WACC"),
            key_on='feature.properties.iso3_code',
            line_opacity=0.8,
            highlight=True,
            fill_color="YlGnBu",
            nan_fill_color = "grey",
            legend_name="Weighted Average Cost of Capital (%)"
        )
        choropleth.geojson.add_to(map)


        df_indexed = df.set_index('iso3_code')
        df_indexed = df_indexed.dropna(subset="WACC")
        for feature in choropleth.geojson.data['features']:
            iso3_code = feature['properties']['iso3_code']
            feature['properties'][technology + ' WACC'] = (
            f"{df_indexed.loc[iso3_code, 'WACC']:0.2f}%" if iso3_code in df_indexed.index else "N/A"
        )
            feature['properties']["Debt_Share"] = (
            f"{df_indexed.loc[iso3_code, 'Debt_Share']:0.2f}%" if iso3_code in df_indexed.index else "N/A"
        )
            feature['properties']["Equity_Cost"] = (
            f"{df_indexed.loc[iso3_code, 'Equity_Cost']:0.2f}%" if iso3_code in df_indexed.index else "N/A"
        )
            feature['properties']["Debt_Cost"] = (
            f"{df_indexed.loc[iso3_code, 'Debt_Cost']:0.2f}%" if iso3_code in df_indexed.index else "N/A"
        )
            feature['properties']["Tax_Rate"] = (
            f"{df_indexed.loc[iso3_code, 'Tax_Rate']:0.2f}%" if iso3_code in df_indexed.index else "N/A"
        )
            #feature['properties']['GDP'] = 'GDP: ' + '{:,}'.format(df_indexed.loc[country_name, 'State Pop'][0]) if country_name in list(df_indexed.index) else ''

        #choropleth.geojson.add_child(
            #folium.features.GeoJsonTooltip(['english_short'], labels=False)
        #)

        choropleth.geojson.add_child(
        folium.features.GeoJsonTooltip(
            fields=['english_short', technology + ' WACC', "Equity_Cost", "Debt_Cost", "Debt_Share", "Tax_Rate"],  # Display these fields
            aliases=["Country:", technology + ":", "Cost of Equity:", "Cost of Debt:", "Debt Share:", "Tax_Rate"],         # Display names for the fields
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
        
        st_map = st_folium(map, width=700, height=350)

        country_name = ''
        if st_map['last_active_drawing']:
            country_name = st_map['last_active_drawing']['properties']['english_short']
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
