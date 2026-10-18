# HTTP Garden — adaptation Windows

Fork adapté pour Windows (Docker Desktop + WSL2) de **[The HTTP Garden](https://github.com/narfindustries/http-garden)**, un outil de fuzzing différentiel qui compare la façon dont des serveurs et proxys HTTP/1.1 interprètent la même requête.

> **Crédit.** Le projet original est l'œuvre de **Ben Kallus** (Dartmouth College) et des contributeurs de [narfindustries/http-garden](https://github.com/narfindustries/http-garden), sous licence **GPL-3.0**. Ce dépôt ne fait qu'adapter l'outil à Windows. Article de recherche : [arXiv 2405.17737](https://arxiv.org/abs/2405.17737).

## C'est quoi ?

Une collection de serveurs (Gunicorn, Nginx, Hyper, etc.) et de proxys (HAProxy, Nginx en reverse proxy, etc.), chacun dans son conteneur Docker, avec un REPL Python pour leur envoyer des requêtes brutes et **comparer leurs interprétations**.

Pourquoi c'est utile : quand deux maillons d'une chaîne (proxy → serveur) ne lisent pas une requête de la même façon, on peut obtenir du **HTTP request smuggling**, des contournements d'ACL ou des dénis de service. Le Garden sert à repérer ces divergences.

## Ce qui change par rapport à l'original

| Modification | Détail |
|---|---|
| **Ports exposés** | Chaque service expose son port sur l'hôte (ex. `hyper` → 8080, `nginx` → 8081). |
| **`targets.py`** | Utilise `127.0.0.1` et les ports hôtes pour les services listés dans `HOST_PORTS`. |
| **Timeout** | `_DEFAULT_SERVER_TIMEOUT` passe à 5 secondes. |
| **Chemins** | Chemins absolus via `Path(__file__).resolve()`. |

## Installation

**Prérequis :** Windows 10/11, [Docker Desktop](https://www.docker.com/products/docker-desktop/) avec WSL2, Python 3.

```bash
pip install docker pyyaml tqdm
```

```bash
# 1. Image de base
docker build ./images/http-garden-soil -t http-garden-soil

# 2. Cibles (la compilation prend plusieurs minutes)
docker compose build hyper nginx gunicorn nginx_proxy haproxy
```

## Utilisation

```bash
docker compose up -d hyper nginx gunicorn nginx_proxy haproxy
python tools/repl.py
```

Dans le REPL :

```text
garden> payload 'POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\n0\n\r\n'
garden> servers gunicorn hyper nginx
garden> grid
```

`grid` affiche une matrice ✅/❌ : ❌ signifie que deux serveurs interprètent la requête différemment. Ici, Nginx accepte `\n` comme fin de ligne dans un chunk, pas Gunicorn ni Hyper.

## Limites connues

- **`transduce` renvoie une erreur 400** avec les transducteurs `haproxy` et `nginx_proxy`. Investigation en cours.
- Seules quelques cibles sont testées sous Windows ; les autres ne sont pas garanties.

## Usage responsable

N'envoie ces payloads **qu'à tes propres conteneurs locaux** ou à des systèmes pour lesquels tu as une autorisation écrite.

## Pour aller plus loin

- Dépôt original, liste des cibles et bugs trouvés : [narfindustries/http-garden](https://github.com/narfindustries/http-garden)
- Article : [The HTTP Garden: Discovering Parsing Vulnerabilities in HTTP/1.1 Implementations by Differential Fuzzing of Request Streams](https://arxiv.org/abs/2405.17737)

## Licence et remerciements

Distribué sous **GPL-3.0**, comme le projet d'origine.

Le projet original est basé sur des travaux soutenus par la DARPA (contrat HR0011-19-C-0076) et remercie Galois, Trail of Bits, Narf Industries et Dartmouth College.
