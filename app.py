
import streamlit as st
import pandas as pd
import requests
import math
from datetime import date

st.set_page_config(
    page_title="Greecon Valley",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Greecon Valley")
st.subheader("Climate Adaptation Platform")

st.write(
    "Understand the climate. Take care of your land."
    "Make better decisions with NASA data."
)

st.info(
    "April Fools is a data-driven agricultural decision-support "
    "designed to help farmers adapt to changing "
    "climate conditions."
)


CROPS = {
    "Wheat": {
        "kc": [0.35, 0.75, 1.15, 0.45],
        "duration": 8,
        "planting_month": 10,
        "temperature": [8, 22],
        "rainfall": [250, 650],
        "family": "Cereal",
        "alternatives": ["Chickpea", "Lentil", "Sunflower"]
    },
    "Barley": {
        "kc": [0.35, 0.75, 1.15, 0.45],
        "duration": 7,
        "planting_month": 10,
        "temperature": [5, 22],
        "rainfall": [200, 550],
        "family": "Cereal",
        "alternatives": ["Chickpea", "Lentil", "Sunflower"]
    },
    "Corn": {
        "kc": [0.40, 0.80, 1.15, 0.70],
        "duration": 5,
        "planting_month": 4,
        "temperature": [18, 30],
        "rainfall": [400, 800],
        "family": "Cereal",
        "alternatives": ["Soybean", "Wheat", "Chickpea"]
    },
    "Chickpea": {
        "kc": [0.40, 0.75, 1.00, 0.35],
        "duration": 4,
        "planting_month": 3,
        "temperature": [10, 25],
        "rainfall": [200, 500],
        "family": "Legume",
        "alternatives": ["Wheat", "Barley", "Sunflower"]
    },
    "Lentil": {
        "kc": [0.45, 0.75, 1.10, 0.50],
        "duration": 5,
        "planting_month": 11,
        "temperature": [8, 23],
        "rainfall": [200, 500],
        "family": "Legume",
        "alternatives": ["Wheat", "Barley", "Sunflower"]
    },
    "Soybean": {
        "kc": [0.35, 0.75, 1.10, 0.60],
        "duration": 5,
        "planting_month": 5,
        "temperature": [18, 30],
        "rainfall": [400, 800],
        "family": "Legume",
        "alternatives": ["Wheat", "Barley", "Sunflower"]
    },
    "Sunflower": {
        "kc": [0.35, 0.75, 1.15, 0.55],
        "duration": 5,
        "planting_month": 4,
        "temperature": [15, 28],
        "rainfall": [300, 700],
        "family": "Oilseed",
        "alternatives": ["Wheat", "Barley", "Chickpea"]
    },
    "Cotton": {
        "kc": [0.45, 0.75, 1.15, 0.75],
        "duration": 6,
        "planting_month": 4,
        "temperature": [20, 32],
        "rainfall": [500, 1000],
        "family": "Industrial crop",
        "alternatives": ["Wheat", "Chickpea", "Soybean"]
    }
}

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December"
]

MONTH_NAMES = {
    i + 1: month for i, month in enumerate(MONTHS)
}

@st.cache_data(ttl=86400)
def load_provinces():

    url = (
        "https://raw.githubusercontent.com/"
        "open-admin-data/turkey-administrative-divisions/"
        "master/data/all-province.json"
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    records = response.json()

    provinces = {}

    for province in records:

        name = province["name"]["local"]

        provinces[name] = {
            "latitude": float(province["geo"]["lat"]),
            "longitude": float(province["geo"]["lon"])
        }

    return provinces


@st.cache_data(ttl=3600)
def get_nasa_data(latitude, longitude, start_date, end_date):

    url = (
        "https://power.larc.nasa.gov/api/"
        "temporal/daily/point"
    )

    parameters = {
        "parameters": (
            "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,"
            "RH2M,WS2M,ALLSKY_SFC_SW_DWN,PS"
        ),
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": start_date,
        "end": end_date,
        "format": "JSON",
        "time-standard": "LST"
    }

    response = requests.get(
        url,
        params=parameters,
        timeout=90
    )

    response.raise_for_status()

    data = response.json()
    climate = data["properties"]["parameter"]

    df = pd.DataFrame(climate)

    df.index = pd.to_datetime(
        df.index,
        format="%Y%m%d"
    )

    df = df.sort_index()
    df = df.replace(-999, float("nan"))

    required_columns = [
        "T2M",
        "T2M_MAX",
        "T2M_MIN",
        "PRECTOTCORR",
        "RH2M",
        "WS2M",
        "ALLSKY_SFC_SW_DWN",
        "PS"
    ]

    df = df.dropna(subset=required_columns)

    if df.empty:
        raise ValueError(
            "No usable NASA climate records were returned."
        )

    return df


def calculate_et0(df, latitude):

    latitude_rad = math.radians(latitude)

    def calculate_day(timestamp, row):

        temp = row["T2M"]
        temp_max = row["T2M_MAX"]
        temp_min = row["T2M_MIN"]

        humidity = row["RH2M"]
        wind = row["WS2M"]
        radiation = row["ALLSKY_SFC_SW_DWN"]
        pressure = row["PS"]

        day_of_year = timestamp.dayofyear

        if temp <= -273 or temp_max <= -273 or temp_min <= -273:
            return float("nan")

        if radiation < 0 or pressure <= 0:
            return float("nan")

        dr = (
            1 + 0.033 * math.cos(
                2 * math.pi * day_of_year / 365
            )
        )

        solar_declination = (
            0.409 * math.sin(
                2 * math.pi * day_of_year / 365 - 1.39
            )
        )

        cos_ws = (
            -math.tan(latitude_rad)
            * math.tan(solar_declination)
        )

        cos_ws = max(-1, min(1, cos_ws))

        sunset_angle = math.acos(cos_ws)

        ra = (
            (24 * 60 / math.pi)
            * 0.0820
            * dr
            * (
                sunset_angle
                * math.sin(latitude_rad)
                * math.sin(solar_declination)
                +
                math.cos(latitude_rad)
                * math.cos(solar_declination)
                * math.sin(sunset_angle)
            )
        )

        es_max = 0.6108 * math.exp(
            17.27 * temp_max / (temp_max + 237.3)
        )

        es_min = 0.6108 * math.exp(
            17.27 * temp_min / (temp_min + 237.3)
        )

        es = (es_max + es_min) / 2

        ea = es * humidity / 100

        delta = (
            4098
            * (
                0.6108
                * math.exp(
                    17.27 * temp / (temp + 237.3)
                )
            )
            / ((temp + 237.3) ** 2)
        )

        gamma = 0.000665 * pressure

        rso = 0.75 * ra

        if rso <= 0:
            return 0.0

        radiation_ratio = min(
            max(radiation / rso, 0),
            1
        )

        temp_max_k = temp_max + 273.16
        temp_min_k = temp_min + 273.16

        rnl = (
            4.903e-9
            * (
                (temp_max_k ** 4 + temp_min_k ** 4) / 2
            )
            * (0.34 - 0.14 * math.sqrt(max(ea, 0)))
            * (1.35 * radiation_ratio - 0.35)
        )

        rn = 0.77 * radiation - rnl

        et0 = (
            0.408 * delta * rn
            +
            gamma
            * (900 / (temp + 273))
            * wind
            * (es - ea)
        ) / (
            delta
            + gamma * (1 + 0.34 * wind)
        )

        return max(0, et0)

    result = df.copy()

    result["ET0"] = [
        calculate_day(timestamp, row)
        for timestamp, row in result.iterrows()
    ]

    result = result.dropna(subset=["ET0"])

    if result.empty:
        raise ValueError(
            "Reference evapotranspiration could not be calculated."
        )

    return result


def calculate_kc(crop, planting_month, timestamp):

    crop_info = CROPS[crop]

    coefficients = crop_info["kc"]
    duration = crop_info["duration"]

    month_difference = (
        timestamp.month - planting_month
    ) % 12

    if month_difference >= duration:
        return 0.0

    if duration <= 1:
        return coefficients[2]

    progress = month_difference / max(duration - 1, 1)

    if progress < 0.20:
        return coefficients[0]

    elif progress < 0.40:
        return (
            coefficients[0]
            + (coefficients[1] - coefficients[0])
            * ((progress - 0.20) / 0.20)
        )

    elif progress < 0.75:
        return coefficients[2]

    else:
        return (
            coefficients[2]
            + (coefficients[3] - coefficients[2])
            * ((progress - 0.75) / 0.25)
        )


def analyze_crop_water(df, crop, planting_month):

    result = df.copy()

    result["Kc"] = [
        calculate_kc(crop, planting_month, timestamp)
        for timestamp in result.index
    ]

    result["ETc"] = result["ET0"] * result["Kc"]

    result["Estimated_Effective_Rainfall"] = (
        result["PRECTOTCORR"] * 0.80
    )

    result["Water_Balance"] = (
        result["ETc"]
        - result["Estimated_Effective_Rainfall"]
    )

    result["Water_Deficit_Indicator"] = (
        result["Water_Balance"].clip(lower=0)
    )

    result["Month"] = [
        MONTH_NAMES[timestamp.month]
        for timestamp in result.index
    ]

    monthly = result.groupby("Month").agg({
        "T2M": "mean",
        "T2M_MAX": "max",
        "T2M_MIN": "min",
        "PRECTOTCORR": "sum",
        "RH2M": "mean",
        "WS2M": "mean",
        "ET0": "sum",
        "ETc": "sum",
        "Estimated_Effective_Rainfall": "sum",
        "Water_Deficit_Indicator": "sum"
    })

    monthly = monthly.reindex(MONTHS).fillna(0)

    return result, monthly


def calculate_suitability(
    crop,
    monthly,
    planting_month,
    temperature_change=0,
    rainfall_change=0
):

    crop_info = CROPS[crop]
    duration = crop_info["duration"]

    season_indices = [
        (planting_month + i - 1) % 12
        for i in range(duration)
    ]

    season = monthly.iloc[season_indices]

    average_temperature = (
        season["T2M"].mean()
        + temperature_change
    )

    seasonal_rainfall = (
        season["PRECTOTCORR"].sum()
        * (1 + rainfall_change / 100)
    )

    min_temp, max_temp = crop_info["temperature"]
    min_rain, max_rain = crop_info["rainfall"]

    if min_temp <= average_temperature <= max_temp:
        temperature_score = 100

    elif average_temperature < min_temp:
        temperature_score = max(
            0,
            100 - (min_temp - average_temperature) * 8
        )

    else:
        temperature_score = max(
            0,
            100 - (average_temperature - max_temp) * 8
        )

    if min_rain <= seasonal_rainfall <= max_rain:
        rainfall_score = 100

    elif seasonal_rainfall < min_rain:
        rainfall_score = max(
            0,
            100 - (min_rain - seasonal_rainfall) * 0.15
        )

    else:
        rainfall_score = max(
            0,
            100 - (seasonal_rainfall - max_rain) * 0.10
        )

    seasonal_deficit = season[
        "Water_Deficit_Indicator"
    ].sum()

    seasonal_etc = season["ETc"].sum()

    if seasonal_etc > 0:
        deficit_ratio = min(
            seasonal_deficit / seasonal_etc,
            1
        )
    else:
        deficit_ratio = 0

    water_score = max(
        0,
        100 - deficit_ratio * 100
    )

    total_score = (
        temperature_score * 0.40
        + rainfall_score * 0.30
        + water_score * 0.30
    )

    return {
        "score": round(total_score),
        "temperature": round(temperature_score),
        "rainfall": round(rainfall_score),
        "water": round(water_score),
        "season_temperature": average_temperature,
        "season_rainfall": seasonal_rainfall,
        "season_deficit": seasonal_deficit
    }



def calculate_alternatives(crop, monthly):

    candidates = CROPS[crop]["alternatives"]

    results = []

    for candidate in candidates:

        assessment = calculate_suitability(
            candidate,
            monthly,
            CROPS[candidate]["planting_month"]
        )

        results.append({
            "Crop": candidate,
            "Preliminary Score": assessment["score"],
            "Crop Family": CROPS[candidate]["family"]
        })

    return pd.DataFrame(results).sort_values(
        "Preliminary Score",
        ascending=False
    )



st.sidebar.header("🌾 Farm Profile")

try:
    provinces = load_provinces()

except Exception as error:
    st.error(f"Could not load province data: {error}")
    st.stop()

selected_province = st.sidebar.selectbox(
    "Select your province",
    sorted(provinces.keys())
)

province_latitude = provinces[selected_province]["latitude"]
province_longitude = provinces[selected_province]["longitude"]

use_farm_coordinates = st.sidebar.checkbox(
    "Use my actual farm coordinates"
)

if use_farm_coordinates:

    latitude = st.sidebar.number_input(
        "Farm latitude",
        min_value=-90.0,
        max_value=90.0,
        value=float(province_latitude),
        format="%.5f"
    )

    longitude = st.sidebar.number_input(
        "Farm longitude",
        min_value=-180.0,
        max_value=180.0,
        value=float(province_longitude),
        format="%.5f"
    )

else:
    latitude = province_latitude
    longitude = province_longitude

st.sidebar.caption(
    f"Coordinates: {latitude:.4f}, {longitude:.4f}"
)

selected_crop = st.sidebar.selectbox(
    "Select your crop",
    list(CROPS.keys())
)

planting_month = st.sidebar.selectbox(
    "Planting month",
    list(range(1, 13)),
    index=CROPS[selected_crop]["planting_month"] - 1,
    format_func=lambda month: MONTH_NAMES[month]
)

soil_type = st.sidebar.selectbox(
    "Soil type",
    ["Clay", "Sandy", "Loamy", "Silty"]
)

water_access = st.sidebar.selectbox(
    "Water availability",
    ["High", "Medium", "Low"]
)

priority = st.sidebar.selectbox(
    "Your agricultural priority",
    [
        "Water conservation",
        "Soil health",
        "Crop diversity"
    ]
)

st.sidebar.divider()

st.sidebar.subheader("🌡️ Climate Stress Test")

temperature_scenario = st.sidebar.selectbox(
    "Hypothetical temperature change",
    [0, 1, 1.5, 2, 3],
    format_func=lambda value: f"+{value} °C"
)

rainfall_scenario = st.sidebar.selectbox(
    "Hypothetical rainfall change",
    [0, -10, -20, -30, 10],
    format_func=lambda value: f"{value:+}%"
)

st.sidebar.caption(
    "These are hypothetical stress-test assumptions, "
    "not NASA climate projections."
)

analyze_button = st.sidebar.button(
    "🌍 Analyze My Farm",
    use_container_width=True
)


if analyze_button:

    with st.spinner(
        "Retrieving NASA data and analyzing climate conditions..."
    ):

        try:

            # Use the most recently completed calendar year.
            analysis_year = date.today().year - 1

            start_date = f"{analysis_year}0101"
            end_date = f"{analysis_year}1231"

            raw_data = get_nasa_data(
                latitude,
                longitude,
                start_date,
                end_date
            )

            df = calculate_et0(
                raw_data,
                latitude
            )

            result, monthly = analyze_crop_water(
                df,
                selected_crop,
                planting_month
            )

            suitability = calculate_suitability(
                selected_crop,
                monthly,
                planting_month
            )

            stress_test = calculate_suitability(
                selected_crop,
                monthly,
                planting_month,
                temperature_scenario,
                rainfall_scenario
            )

            alternatives = calculate_alternatives(
                selected_crop,
                monthly
            )

            st.success(
                f"NASA climate data analyzed for {selected_province}."
            )

            st.caption(
                f"Analysis period: {analysis_year}. "
                "These are historical observations, not forecasts."
            )


            st.header("Climate Overview")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Average Temperature",
                    f"{df['T2M'].mean():.1f} °C"
                )

            with col2:
                st.metric(
                    "Total Rainfall",
                    f"{df['PRECTOTCORR'].sum():.1f} mm"
                )

            with col3:
                st.metric(
                    "Average Relative Humidity",
                    f"{df['RH2M'].mean():.1f}%"
                )

            with col4:
                st.metric(
                    "Total Reference ET0",
                    f"{df['ET0'].sum():.1f} mm"
                )


            st.header("Monthly Climate Analysis")

            st.subheader("Average Monthly Temperature")

            st.line_chart(
                monthly["T2M"],
                y_label="Temperature (°C)"
            )

            st.subheader("Monthly Rainfall")

            st.bar_chart(
                monthly["PRECTOTCORR"],
                y_label="Rainfall (mm)"
            )

            st.subheader("Monthly Reference Water Demand")

            st.bar_chart(
                monthly["ET0"],
                y_label="ET0 (mm)"
            )


            st.divider()

            st.header("Crop-Specific Water Analysis")

            st.write(
                f"Selected crop: **{selected_crop}**"
            )

            total_etc = result["ETc"].sum()

            total_rainfall = result["PRECTOTCORR"].sum()

            total_deficit = (
                result["Water_Deficit_Indicator"].sum()
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Estimated Crop Water Use",
                    f"{total_etc:.1f} mm"
                )

            with col2:
                st.metric(
                    "Total Rainfall",
                    f"{total_rainfall:.1f} mm"
                )

            with col3:
                st.metric(
                    "Rainfall Deficit Indicator",
                    f"{total_deficit:.1f} mm"
                )

            st.caption(
                "ETc = ET0 × Kc. Effective rainfall is estimated "
                "as 80% of total rainfall. This is not an actual "
                "irrigation requirement. Soil water storage, runoff, "
                "drainage and irrigation inputs are not included."
            )

            st.subheader("Monthly Crop Water Use")

            st.bar_chart(
                monthly["ETc"],
                y_label="ETc (mm)"
            )

            st.subheader("Rainfall vs. Crop Water Use")

            water_chart = monthly[
                ["PRECTOTCORR", "ETc"]
            ].rename(
                columns={
                    "PRECTOTCORR": "Rainfall",
                    "ETc": "Crop Water Use"
                }
            )

            st.line_chart(
                water_chart,
                y_label="Water amount (mm)"
            )

            st.divider()

            st.header("Crop Suitability Assessment")

            score = suitability["score"]

            st.metric(
                "Preliminary Suitability Score",
                f"{score}/100"
            )

            st.progress(score / 100)

            if score >= 75:

                st.success(
                    "The selected reference ranges indicate "
                    "generally favorable climate conditions."
                )

            elif score >= 50:

                st.warning(
                    "Some climate conditions may create risks "
                    "for this crop. Local agricultural data "
                    "should be reviewed."
                )

            else:

                st.error(
                    "The selected reference ranges indicate "
                    "potential climate mismatches."
                )

            st.write("**Score Components**")

            score_data = pd.DataFrame({
                "Assessment": [
                    "Temperature",
                    "Rainfall",
                    "Water Balance"
                ],
                "Score": [
                    suitability["temperature"],
                    suitability["rainfall"],
                    suitability["water"]
                ]
            })

            st.bar_chart(
                score_data.set_index("Assessment")
            )

            st.write(
                f"- Average seasonal temperature: "
                f"{suitability['season_temperature']:.1f} °C"
            )

            st.write(
                f"- Seasonal rainfall: "
                f"{suitability['season_rainfall']:.1f} mm"
            )

            st.write(
                f"- Seasonal rainfall deficit indicator: "
                f"{suitability['season_deficit']:.1f} mm"
            )

            st.caption(
                "This is an experimental screening indicator based "
                "on broad reference ranges. It does not include "
                "soil pH, salinity, crop variety, disease, frost risk, "
                "altitude or local planting calendars. It should not "
                "be used as the sole basis for planting decisions."
            )

            st.divider()

            st.header("Farmer Action Plan")

            st.write(
                "Actions to consider based on your farm profile "
                "and the available climate data:"
            )

            if total_deficit > 100:

                st.warning(
                    "The rainfall deficit indicator is high. "
                    "Monitor soil moisture and review your "
                    "irrigation schedule using local conditions."
                )

            elif total_deficit > 0:

                st.info(
                    "Rainfall may not fully meet estimated crop "
                    "water use. Verify irrigation needs with "
                    "soil-moisture measurements."
                )

            else:

                st.success(
                    "No rainfall deficit was indicated by this "
                    "simplified calculation. Continue monitoring "
                    "soil moisture."
                )

            if water_access == "Low":

                st.write(
                    "**Limited water availability:** Consider "
                    "drip irrigation, mulching and improved "
                    "irrigation scheduling."
                )

            elif water_access == "Medium":

                st.write(
                    "**Moderate water availability:** Adjust "
                    "irrigation according to crop growth stages "
                    "and soil moisture."
                )

            else:

                st.write(
                    "**High water availability:** Maintain "
                    "efficient water use and monitor consumption."
                )

            if soil_type == "Clay":

                st.write(
                    "**Clay soil:** Monitor drainage and avoid "
                    "heavy field operations when the soil is too wet."
                )

            elif soil_type == "Sandy":

                st.write(
                    "**Sandy soil:** Water retention may be lower. "
                    "Consider monitoring soil moisture and improving "
                    "organic matter."
                )

            elif soil_type == "Loamy":

                st.write(
                    "**Loamy soil:** Focus on maintaining "
                    "organic matter and healthy soil structure."
                )

            else:

                st.write(
                    "**Silty soil:** Monitor erosion and drainage, "
                    "especially after heavy rainfall."
                )

            if priority == "Water conservation":

                st.write(
                    "Your priority is water conservation. "
                    "Consider drip irrigation, mulching and "
                    "improved irrigation timing."
                )

            elif priority == "Soil health":

                st.write(
                    "Your priority is soil health. Consider soil "
                    "testing, organic matter management and "
                    "appropriate crop rotation."
                )

            else:

                st.write(
                    "Your priority is crop diversity. Research "
                    "alternative crops, local planting calendars "
                    "and market conditions."
                )


            st.divider()

            st.header("Alternative Crops and Rotation Ideas")

            st.write(
                "The following crops are potential alternatives "
                "to consider for your current crop."
            )

            st.dataframe(
                alternatives,
                use_container_width=True,
                hide_index=True
            )

            st.info(
                "A reliable crop rotation plan must consider "
                "crop families, disease cycles, soil nutrients, "
                "water requirements and local planting calendars. "
                "This list is not a confirmed planting recommendation."
            )


            st.divider()

            st.header("Climate Change Stress Test")

            st.write(
                "Explore how hypothetical temperature and rainfall "
                "changes affect the preliminary suitability indicator."
            )

            col1, col2 = st.columns(2)

            with col1:
                st.metric(
                    "Current Conditions",
                    f"{suitability['score']}/100"
                )

            with col2:
                st.metric(
                    "Stress Test Result",
                    f"{stress_test['score']}/100",
                    delta=(
                        stress_test["score"]
                        - suitability["score"]
                    )
                )

            st.write(
                f"Assumptions: temperature +{temperature_scenario} °C, "
                f"rainfall {rainfall_scenario:+}%."
            )

            st.caption(
                "This is a hypothetical stress test, not a NASA "
                "climate projection or a forecast of future conditions."
            )


            st.divider()

            st.header("Monthly Climate Data")

            display_data = monthly.rename(
                columns={
                    "T2M": "Average Temperature (°C)",
                    "T2M_MAX": "Maximum Temperature (°C)",
                    "T2M_MIN": "Minimum Temperature (°C)",
                    "PRECTOTCORR": "Rainfall (mm)",
                    "RH2M": "Relative Humidity (%)",
                    "WS2M": "Wind Speed (m/s)",
                    "ET0": "Reference ET0 (mm)",
                    "ETc": "Crop ETc (mm)",
                    "Estimated_Effective_Rainfall": "Estimated Effective Rainfall (mm)",
                    "Water_Deficit_Indicator": "Water Deficit Indicator (mm)"
                }
            )

            st.dataframe(
                display_data.round(2),
                use_container_width=True
            )

            st.subheader("Download Your Data")

            csv_data = result.to_csv(
                index=True
            ).encode("utf-8-sig")

            st.download_button(
                label="Download Analysis as CSV",
                data=csv_data,
                file_name="farmsight_analysis.csv",
                mime="text/csv"
            )


            with st.expander(
                "View Daily NASA Data"
            ):

                st.dataframe(
                    result.round(3),
                    use_container_width=True
                )

        except Exception as error:

            st.error(
                f"An error occurred during analysis: {error}"
            )

            st.info(
                "Check your internet connection, NASA API access "
                "and selected coordinates."
            )


st.sidebar.divider()

st.sidebar.caption(
    "Climate data: NASA POWER"
)

st.sidebar.caption(
    "Evapotranspiration method: FAO-56 approach"
)

st.sidebar.caption(
    "Crop coefficients: General reference inputs "
    "used in this prototype"
)

st.sidebar.caption(
    "Province coordinates: Open Admin Data"
)

st.sidebar.caption(
    "FARMSIGHT | Data-driven solutions for the future of agriculture"
)

st.divider()

st.caption(
    "FARMSIGHT is a research and decision-support prototype. "
    "Its results do not replace professional agricultural advice "
    "or local soil testing."
)
