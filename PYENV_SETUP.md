# Pyenv environment setup (alongside Anaconda)

This project can use either **Anaconda** (`conda activate esb-gpt`) or **pyenv** with a virtualenv. Use one or the other in a given terminal session.

## Prerequisites (one-time, if pyenv is not installed)

```bash
# Install pyenv (macOS with Homebrew)
brew install pyenv

# Add to ~/.zshrc (or ~/.bash_profile) and restart shell
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
```

Restart your terminal or run `source ~/.zshrc`.

## Create the project environment (one-time per machine)

1. **Install Python 3.10 via pyenv (one-time):**
   ```bash
   pyenv install 3.10.13
   ```

2. **Set project Python and create a virtualenv:**
   ```bash
   cd /Users/a13406882/hackathon/ESB-GPT
   pyenv local 3.10.13
   python -m venv .venv
   ```

3. **Activate and install dependencies:**
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run the app** (same as with Conda):
   ```bash
   uvicorn app.main:app --reload
   ```

## Start the environment (every new shell)

```bash
cd /Users/a13406882/hackathon/ESB-GPT
source .venv/bin/activate
```

Then run the app or any project commands as usual.

## Coexistence with Anaconda

- **Conda:** `conda activate esb-gpt` uses the env from `environment.yml`.
- **Pyenv:** `source .venv/bin/activate` uses the venv created with pyenv’s Python 3.10 and `requirements.txt`.

The `.python-version` file in this directory tells pyenv which Python to use here; it does not affect Conda.
