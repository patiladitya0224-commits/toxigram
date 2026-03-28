"""
Run this ONCE before starting ToxiGram to download NLTK data.
Command: python setup.py
"""
import nltk
import subprocess
import sys

print("🔧 ToxiGram Setup Script")
print("=" * 40)

# Download NLTK packages
nltk_packages = ['vader_lexicon', 'wordnet', 'averaged_perceptron_tagger', 'punkt', 'omw-1.4']
print("\n📦 Downloading NLTK data...")
for pkg in nltk_packages:
    try:
        nltk.download(pkg, quiet=False)
        print(f"  ✅ {pkg}")
    except Exception as e:
        print(f"  ⚠️  {pkg} — {e}")

# TextBlob corpora
print("\n📦 Downloading TextBlob corpora...")
try:
    subprocess.run([sys.executable, '-m', 'textblob.download_corpora'], check=True)
    print("  ✅ TextBlob corpora")
except Exception as e:
    print(f"  ⚠️  TextBlob — {e}")

print("\n✅ Setup complete! Now run: python app.py")
print("🌐 Open http://127.0.0.1:5000 in your browser")
