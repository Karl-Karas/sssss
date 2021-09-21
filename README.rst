Barebone server to share and play with Mathieu Jadin Simulacres Dynamic sheets, ... and get some stats too !

SimulacreS Sheet Sharing Server
===============================

Un serveur très simple pour récupérer les `fiches SimulacreS dynamiques
<https://github.com/jadinm/simulacres-dynamic-sheet>`_ de Mathieu Jadin, afin
que la meneuse ou le DM puisse les avoir sous les yeux facilement.  A terme, on
peut imaginer de recevoir en direct les modifications, à la DnDBeyond©™, ce qui
sera utile aussi bien autour de la table qu'en mode distanciel (j'ai dit « à
terme », on est loin du compte actuellement ;-)).

Contrairement à la fiche dynamique qui est un formidable cadeau à mettre entre
les mains de toutes les joueuses et tous les joueurs, l'installation et
l'hébergement de cet applicatif demande une certaine expérience en
informatique. Si jamais vous souhaitez tester le machin, contactez Karl Karas
via le groupe Facebook Simulacres afin qu'il vous héberge une campagne sur son
serveur semi-public.

Installation
------------

::

  $ python3.8 -m venv venv
  $ . ./venv/bin/activate
  (venv) $ pip install -r requirements.txt

Et pour lancer le serveur de test ::

  (venv) export DMVIEW_CONFIGFILE=config.ini; python dmview.py 

(à ne pas utiliser en production, you know the drill...)

Déploiement
-----------

C'est une application WSGI écrite avec Flask. On peut trouver `dans la doc
<https://flask.palletsprojects.com/en/1.1.x/deploying/>`_  quelques exemples de
déploiements.

C'est testé avec `Gunicorn <https://gunicorn.org>`_ et `Apache
<https://httpd.apache.org/docs/2.4/fr/mod/mod_proxy.html>`_ comme proxy.

A priori, je ne pense pas qu'il existe actuellement un moyen vraiment « simple
» d'héberger ce genre d'application.

Utilisation
-----------

Donc, il faut que vos joueurs utilisent la fiche dynamique de Mathieu, **et
qu'ils importent le plugin d'exportation vers un serveur**, via le bouton en
bas de page (à droite). Ce `plugin
<https://github.com/jadinm/simulacres-dynamic-sheet/blob/main/plugins/plugin_export_to_server.html>`_
est disponible dans le dépôt de Mathieu : il faut le télécharger et
l'enregistrer sur son disque pour pouvoir l'importer. Son importation
provoquera l'apparition d'un nouvel onglet nommé « Exporter » sur la fiche.

Une fois que c'est fait, la base de l'API c'est précisément de pouvoir recevoir
ces fiches. L'URL à indiquer dans l'onglet Exporter est quelque chose comme ::

  https://url_de_mon_serveur.org/push/<identifiant campagne>/<identifiant perso>

où

- ``url_de_mon_serveur.org`` est le nom de domaine où vous hébergez le serveur
- ``<identifiant campagne>`` est n'importe quelle chaîne de caractères qui
  serve à identifier votre campagne en cours (ce paramètre est donc commun à
  tous les personnages d'une même campagne)
- ``<identifiant perso>`` est n'importe quelle chaîne de caractères qui serve à
  identifier le personnage (ce paramètre est donc unique pour un personnage
  donné)

Une fois que c'est exporté vers le serveur, la meneuse ou le DM peut voir la
liste des fiches disponibles pour la campagne et les consulter, ce qui renvoie
tout le contenu de la fiche complète, mise en forme comme la voit la joueuse ou
le joueur (au moment où il l'a exportée)).

Note
----

Pour l'instant c'est moche, mais c'est pas le pire par les temps qui courrent !
Comme on dit à DnD : « Beauty is in the eyes of the Beholder ! » :-P

Simulacres©™ - le jeu de rôle élémentaire a été créé par Pierre Rosenthal.  Les
règles de Simulacres © sont soumises à copyright et Simulacres™ est une marque
déposée.

Ce projet manipule des fiches de personnages dynamiques concues pour faciliter
la gestion d'un personnage dans une campagne de Simulacres mais il ne s'agit
pas de matériel officiel.
