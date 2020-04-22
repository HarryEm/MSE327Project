# Designing Successful Kickstarter Crowdfunding Campaigns: a Causal Inference Approach

This repo contains code in which we analyse the causal effects of various
features in [Kickstarter](https://www.kickstarter.com/) campaigns.
[Here](https://www.kickstarter.com/projects/flairespresso/the-neo-delicious-affordable-espresso-at-home?ref=section-food-craft-featured-project)
is an example of a featured campaign.

Please see the [final report](https://github.com/HarryEm/MSE327Project/blob/master/Final_Report.pdf) for the full writeup of our findings.

## Authors

* **Nicolas Bievre** - [github](https://github.com/nbievre)
* **Harry Emeric** - [github](https://github.com/harryem)

## Data Collection and Preprocessing

The script in

```
python/kickstarter_main.py
```

Contains the methods to collect, clean, and engineer features from the raw data
obtained by a web crawler [here](https://webrobots.io/kickstarter-datasets)

To merge the raw csv files together from webrobots, run

```
# Example
python3 python/kickstarter_main.py --mode merge
```

To collect additional information form the campaign urls directly, run

```
# Example
python3 python/kickstarter_main.py --mode collect --batch 5 --wait 250 --max_request 200
```

To preprocess and clean features, run

```
# Example
python3 python/kickstarter_main.py --mode features
```

## Data Analysis and Visualization

Rmd file for plotting covariates and looking at various interesting
tables summarizing the data can be found in

```
R/Kickstarter_Causal_Analysis.Rmd
```

## Experiments

Rmd file for preparing the data for casual analysis on three chosen
treatment variables and performing hypothesis testing under Fisher and
Neyman frameworks.


```
R/Hypothesis_Testing.Rmd
```
