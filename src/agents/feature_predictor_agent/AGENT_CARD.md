# Agent Feature Engineer + Predicteur

**Role** : prevoit la tendance mensuelle d'un benchmark international du ble
et permet de construire des scenarios de facteurs.
1. Modeles : Prophet sur le log-prix mensuel, momentum 3 mois, persistance et
   baseline saisonniere. Prophet inclut une saisonnalite annuelle et des points
   de rupture.
2. Evaluation : 24 origines glissantes au meme horizon que la prevision; les
   18 premieres servent a choisir le modele par justesse directionnelle (MAPE
   pour departager), les 6 dernieres sont un test final. L'intervalle a 80% est
   calibre uniquement sur les residus de selection.
3. Features : calcule les rendements, la moyenne mobile a 3 mois, la volatilite
   et le momentum.
4. Scenarios : estime les co-mouvements historiques Brent/uree sur 120 mois,
   puis applique les chocs choisis par l'utilisateur. Les autres chocs restent
   des hypotheses explicites et non des effets appris.

**Input** : `CollectorOutput`, `WeatherNewsOutput`

**Output** : `FeaturePredictorOutput` (voir schemas.py)

**Dependances** : prophet, pandas, numpy, scikit-learn

**Limite** : le benchmark World Bank US HRW en USD/tonne n'est ni le prix CIF
tunisien ni une prevision certifiee. Les scores de direction restent indicatifs
et doivent etre evalues sur davantage de fenetres avant tout usage budgetaire.

**Responsable** : [nom]
