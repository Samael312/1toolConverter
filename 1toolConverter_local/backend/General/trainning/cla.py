import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from sentence_transformers import SentenceTransformer
import joblib

# --- 1. Cargar datasets ---
train_df = pd.read_csv("train.csv")
val_df = pd.read_csv("val.csv")

# --- 2. Cargar modelo de embeddings ---
# MiniLM
model_name = "sentence-transformers/all-MiniLM-L6-v2"
embedder = SentenceTransformer(model_name)

# --- 3. Codificar textos ---
X_train = embedder.encode(train_df["text"].tolist(), show_progress_bar=True)
y_train = train_df["label"].tolist()

X_val = embedder.encode(val_df["text"].tolist(), show_progress_bar=True)
y_val = val_df["label"].tolist()

# --- 4. Entrenar RandomForestClassifier ---
clf = RandomForestClassifier(
    n_estimators=200, 
    max_depth=10, 
    random_state=42
)
clf.fit(X_train, y_train)

# --- 5. Evaluar performance ---
y_pred = clf.predict(X_val)
print("Accuracy en validation:", accuracy_score(y_val, y_pred))
print("\nReporte de clasificación:")
print(classification_report(y_val, y_pred))

# --- 6. Guardar modelo y embedder ---
joblib.dump(clf, "cell_type_classifier.pkl")
joblib.dump(embedder, "sentence_embedder.pkl")
print("\n✅ Modelo y embedder guardados como 'cell_type_classifier.pkl' y 'sentence_embedder.pkl'")
