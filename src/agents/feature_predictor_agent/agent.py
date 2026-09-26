import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from src.schemas import CollectorOutput, WeatherNewsOutput, FeaturePredictorOutput
from src.schemas import MatierePremiereOutput


def forecast_copper_prices(
    copper: MatierePremiereOutput,
    horizon_months: int = 6,
) -> pd.DataFrame:
    """Projecte le prix mensuel du cuivre par regression lineaire."""
    if copper.matiere != "cuivre":
        raise ValueError("Cette prevision est reservee a la matiere cuivre.")
    if not 1 <= horizon_months <= 12:
        raise ValueError("L'horizon doit etre compris entre 1 et 12 mois.")

    history = pd.DataFrame(
        [{"date": point.date, "prix_unitaire": point.prix_unitaire} for point in copper.points]
    ).sort_values("date")
    history = history[np.isfinite(history["prix_unitaire"])].reset_index(drop=True)
    if len(history) < 3:
        raise ValueError("Il faut au moins trois observations valides pour prevoir le cuivre.")

    prices = history["prix_unitaire"].to_numpy()
    time_steps = np.arange(len(prices)).reshape(-1, 1)
    model = LinearRegression().fit(time_steps, prices)

    future_steps = np.arange(len(prices), len(prices) + horizon_months).reshape(-1, 1)
    forecast_prices = model.predict(future_steps)
    residual_rmse = np.sqrt(mean_squared_error(prices, model.predict(time_steps)))
    forecast_dates = pd.date_range(
        start=pd.Timestamp(history["date"].iloc[-1]),
        periods=horizon_months + 1,
        freq="MS",
    )[1:]
    leads = np.arange(1, horizon_months + 1)
    uncertainty = 1.96 * residual_rmse * np.sqrt(1 + leads / len(prices))

    return pd.DataFrame(
        {
            "date": forecast_dates.date,
            "prix_prevu_tnd_kg": forecast_prices,
            "borne_basse_indicative": np.maximum(0, forecast_prices - uncertainty),
            "borne_haute_indicative": forecast_prices + uncertainty,
        }
    )


def run(collector: CollectorOutput, weather_news: WeatherNewsOutput) -> FeaturePredictorOutput:
    """Point d entree de l agent Feature Engineer + Predicteur."""
    # TODO etape 1 : calculer les FeatureRow reelles a partir de collector + weather_news
    # TODO etape 2 : entrainer/charger XGBoost par matiere, predire tendance + confiance
    return FeaturePredictorOutput(features=[], predictions=[])
