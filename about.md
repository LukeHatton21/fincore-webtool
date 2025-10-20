# About
FINCORE allows you to estimate the cost of capital for renewable and other power generation projects, for both historical and future time periods, under a range of blended finance structures. It aims to address the limited availability and accessibility of empirical data on clean energy project finance terms, and the geographic skew towards Western and industrialising countries of the limited data that is available.

# Contact
FinCoRE is part of Climate Compatible Growth's suite of open-source Energy Modelling Tools, and has been developed by Luke Hatton at Imperial College London as part of his PhD (focused on energy investment in developing countries). Contact via email at l.hatton23@imperial.ac.uk


# Methodology

The cost of capital is estimated by splitting the overall cost into contributing risk factors, namely:

 * __Risk-free rate__: The global risk-free rate, representing the time value of money. Corresponds to the global macroeconomic interest rate environment and is set based on the U.S. Treasury 10 year bond yield.
 * __Country Risk__: The risk perception of investing in a given country, based on data from financial markets and sovereign credit risk ratings. Country risk estimates are taken from the work of Professor Damodaran at NYU, who evaluates them from sovereign bond credit rating or spreads between the national sovereign bond and US treasury bonds.
 * __Instrument Premium__: The risk premium for equity financing or the lender margin for debt financing, with the equity risk premium set based on existing financial market data and the lender margin assumed to be 2% based on existing data for infrastructure loans.
 * __Technology Risk__: Risks associated with the electricity market and the characteristics of the technology being deployed in a given country. Estimated based on the maturity of the given technology in each national market, taken as the ratio of installed capacity to overall grid capacity, with a continuous interpolation based on existing empirical data on how the market risk premium falls as deployment rises.


 # License
 The data available from this tool is licensed as Creative Commons Attribution-NonCommercial International (CC BY-NC 4.0), which means you are free to copy, redistribute and adapt it for non-commercial purposes, provided you give appropriate credit. If you wish to use the data for commercial purposes, please get in touch.