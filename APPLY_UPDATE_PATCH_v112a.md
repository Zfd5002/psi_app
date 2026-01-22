### v1.1.2a notes (ANARCI install helper)

If you want heavy compute (domains + numbering), after installing Python deps:

```bash
pip install -r requirements.txt -r requirements-heavy.txt
./scripts/install_anarci.sh
```

On Ubuntu, install HMMER if needed:

```bash
sudo apt-get update && sudo apt-get install -y hmmer
```
