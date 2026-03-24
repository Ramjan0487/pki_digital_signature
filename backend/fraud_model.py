import numpy as np, cv2
from tensorflow.keras.models import load_model
model=None
def load():
 global model
 if model is None:
  model=load_model('model/fraud_model.h5')

def predict_fraud(image_file):
 load()
 file_bytes=np.frombuffer(image_file.read(),np.uint8)
 img=cv2.imdecode(file_bytes,cv2.IMREAD_COLOR)
 img=cv2.resize(img,(128,128))/255.0
 img=np.expand_dims(img,0)
 pred=model.predict(img)[0][0]
 return "REAL" if pred<0.5 else "FAKE"
