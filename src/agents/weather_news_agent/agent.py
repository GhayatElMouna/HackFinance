from src.schemas import WeatherNewsOutput


def run(zone: str) -> WeatherNewsOutput:
    """Point d entree de l agent Meteo/News."""
    # TODO: appeler API meteo + API news, calculer score_risque
    return WeatherNewsOutput(score_risque=0.0, events=[], zone=zone)
