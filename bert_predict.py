import torch
import re
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained("./bert_model")
model = AutoModelForSequenceClassification.from_pretrained("./bert_model")

model.to(device)
model.eval()

def normalize_text(text):
    text = text.lower()

    # Step 1: Replace symbol substitutions
    replacements = {
        "@": "a",
        "1": "i",
        "!": "i",
        "$": "s",
        "0": "o",
        "3": "e",
        "7": "t",
        "*": "",
        "#": "",
        "%": "",
        "&": "",
        "^": "",
        "_": "",
        "-": "",
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    # Step 2: Remove non letters except space
    text = re.sub(r'[^a-zA-Z\s]', '', text)

    # Step 3: Fix repeated characters (kiiiill → kill)
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)

    # 🔥 Step 4: Aggressive pattern repair for common bully words
    patterns = {
        r'k+i+l+l+': 'kill',
        r'f+u+c+k+': 'fuck',
        r'r+a+p+e+': 'rape',
        r's+t+a+b+': 'stab',
        r'c+u+t+': 'cut',
        r'd+i+e+': 'die'
    }

    for pattern, word in patterns.items():
        text = re.sub(pattern, word, text)

    # 🔥 Step 5: Fix merged words like "willkillyou"
    text = re.sub(r'willkill', 'will kill', text)
    text = re.sub(r'killyou', 'kill you', text)

    text = re.sub(r'\s+', ' ', text).strip()

    return text


def predict(text):
    cleaned_text = normalize_text(text)

    inputs = tokenizer(
        cleaned_text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=128
    )

    inputs = {key: val.to(device) for key, val in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    prediction = torch.argmax(logits, dim=1).item()

    return prediction
