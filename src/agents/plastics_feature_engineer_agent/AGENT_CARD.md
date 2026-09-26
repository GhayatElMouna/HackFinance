# Agent Feature Engineer Plastiques

**Role** : prepare une serie mensuelle depuis 2000 et construit des features
contemporaines ou retrospectives, sans utiliser de donnees futures. Les cibles
COMEX sont conservees separement par code SH; a defaut, un indice proxy est
calcule avec une ponderation configurable de 70 % Crude_average et 30 % Gas_Europe.

**Entrees** : Pink Sheet (CSV/XLSX), et facultativement importations COMEX,
USD/TND, inflation et droits de douane, charges depuis `data/raw/` ou passees
explicitement au CLI du predicteur.

**Sorties** : `data/processed/features_plastiques.csv`, identifiant de la cible
choisie et liste des colonnes explicatives.

**Methode** : dates ramenees au premier du mois; variations log des energies,
retards, volatilite et ecart a la moyenne de la cible, variables saisonnieres et
series optionnelles disponibles a date. Les labels d'apprentissage sont les
log-variations a 1, 3, 6 et 12 mois, jamais incluses parmi les features.

**Limites** : l'indice est un proxy amont, pas un prix observe de resine. La
normalisation utilise la moyenne 2010; les features de cible sont exprimees en
ratios/log-variations pour ne pas propager cette reference future aux dates
anciennes. La disponibilite intra-mois des publications n'est pas modelisee.