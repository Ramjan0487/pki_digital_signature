from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D,MaxPooling2D,Flatten,Dense
import numpy as np
model=Sequential([
Conv2D(32,(3,3),activation='relu',input_shape=(128,128,3)),
MaxPooling2D(),
Flatten(),
Dense(1,activation='sigmoid')
])
model.compile(optimizer='adam',loss='binary_crossentropy')
X=np.random.rand(50,128,128,3)
y=np.random.randint(0,2,50)
model.fit(X,y,epochs=1)
import os; os.makedirs('model',exist_ok=True)
model.save('model/fraud_model.h5')
