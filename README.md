# 🎈 Blank app template

A simple Streamlit app template for you to modify!

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://blank-app-template.streamlit.app/)

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```

### Run a timeseries calculation

Use `main.py` to calculate `WaccEstimator.calculate_technology_yearly` without
starting Streamlit. Country and technology arguments accept either the display
names used by the app or their codes.

To run directly from PyCharm, edit the configuration values near the top of
`main.py` and run the file. Command-line arguments override those values:

```
$ python main.py \
    --start-year 2020 \
    --end-year 2024 \
    --countries Australia GBR \
    --technology "Solar PV" \
    --concessionality "Commercial Rate" \
    --output solar-timeseries.csv
```

The supported range is 2001-2024. Add `--currency-risk` or `--merchant-risk`
to include those exposures.
