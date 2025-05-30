# -*- coding: utf-8 -*-
"""Untitled3.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1YV2fwJ-5ydI5zmY_ojdelrhJYnUgR-8M
"""

# Import necessary libraries
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.decomposition import PCA
from imblearn.over_sampling import RandomOverSampler
from tensorflow.keras.models import Model
from tensorflow.keras.layers import (
    Input, Dense, Dropout, LSTM, LayerNormalization,
    MultiHeadAttention, Add, Concatenate, Multiply
)
from tensorflow.keras.optimizers import Adam
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report

class HybridLSTMTransformerModel:
    """
    A hybrid model combining LSTM, Transformer, Squeeze-and-Excitation, and Additive Attention
    for classification tasks.
    """

    def __init__(self, n_components=20, lstm_units=64, num_heads=4,
                 ff_dim=128, dropout_rate=0.2, random_state=42):
        """
        Initialize the model parameters

        Parameters:
        -----------
        n_components : int
            Number of PCA components
        lstm_units : int
            Number of LSTM units
        num_heads : int
            Number of attention heads in the transformer
        ff_dim : int
            Feed-forward dimension in the transformer
        dropout_rate : float
            Dropout rate for regularization
        random_state : int
            Random seed for reproducibility
        """
        self.n_components = n_components
        self.lstm_units = lstm_units
        self.num_heads = num_heads
        self.ff_dim = ff_dim
        self.dropout_rate = dropout_rate
        self.random_state = random_state
        self.model = None
        self.history = None
        self.scaler = StandardScaler()
        self.pca = None
        self.label_encoder = LabelEncoder()

    def apply_pca(self, X_train, X_test):
        """
        Apply PCA for dimensionality reduction

        Parameters:
        -----------
        X_train : numpy array
            Training features
        X_test : numpy array
            Testing features

        Returns:
        --------
        X_train_pca : numpy array
            PCA-transformed training features
        X_test_pca : numpy array
            PCA-transformed testing features
        """
        self.pca = PCA(n_components=self.n_components, random_state=self.random_state)
        X_train_pca = self.pca.fit_transform(X_train)
        X_test_pca = self.pca.transform(X_test)

        return X_train_pca, X_test_pca

    def squeeze_and_excitation(self, features, ratio=16):
        """
        Apply Squeeze-and-Excitation block to recalibrate feature maps

        Parameters:
        -----------
        features : numpy array
            Input features (e.g., from PCA)
        ratio : int
            Reduction ratio for the bottleneck

        Returns:
        --------
        scaled : numpy array
            Recalibrated features
        """
        # Reshape for SE block processing (assuming features from PCA)
        se_input = features.reshape(features.shape[0], 1, features.shape[1])

        # Squeeze operation (global average pooling)
        squeeze = np.mean(se_input, axis=1, keepdims=True)

        # Excitation operation (two dense layers with bottleneck)
        reduced_dim = max(1, se_input.shape[2] // ratio)

        # First dense layer with ReLU (manually)
        w1 = np.random.normal(size=(se_input.shape[2], reduced_dim))
        excitation = np.maximum(0, np.dot(squeeze, w1))  # ReLU activation

        # Second dense layer with Sigmoid (manually)
        w2 = np.random.normal(size=(reduced_dim, se_input.shape[2]))
        excitation = 1 / (1 + np.exp(-np.dot(excitation, w2)))  # Sigmoid activation

        # Scale the original features
        scaled = se_input * excitation

        return scaled.reshape(features.shape[0], features.shape[1])

    def transformer_block(self, inputs):
        """
        Transformer block with multi-head self-attention

        Parameters:
        -----------
        inputs : tensor
            Input tensor

        Returns:
        --------
        ff_output : tensor
            Transformer block output
        """
        attention_output = MultiHeadAttention(
            num_heads=self.num_heads,
            key_dim=inputs.shape[-1]
        )(inputs, inputs)

        attention_output = Dropout(self.dropout_rate)(attention_output)
        attention_output = Add()([inputs, attention_output])
        attention_output = LayerNormalization(epsilon=1e-6)(attention_output)

        ff_output = Dense(self.ff_dim, activation='relu')(attention_output)
        ff_output = Dropout(self.dropout_rate)(ff_output)
        ff_output = Dense(inputs.shape[-1])(ff_output)
        ff_output = Add()([attention_output, ff_output])
        ff_output = LayerNormalization(epsilon=1e-6)(ff_output)

        return ff_output

    def additive_attention(self, query, key, value):
        """
        Additive attention mechanism (Bahdanau-style)

        Parameters:
        -----------
        query : tensor
            Query tensor
        key : tensor
            Key tensor
        value : tensor
            Value tensor

        Returns:
        --------
        context_vector : tensor
            Attention-weighted context vector
        """
        # Additive attention uses a feedforward network to compute attention scores
        score = Dense(32, activation='tanh')(Concatenate()([query, key]))
        attention_weights = Dense(1, activation='softmax')(score)
        context_vector = Multiply()([attention_weights, value])

        return context_vector

    def build_model(self, input_shape, num_classes):
        """
        Build the hybrid model architecture

        Parameters:
        -----------
        input_shape : tuple
            Shape of input tensors
        num_classes : int
            Number of target classes

        Returns:
        --------
        model : Keras Model
            Compiled model
        """
        inputs = Input(shape=input_shape)

        # First LSTM layer
        x = LSTM(self.lstm_units, return_sequences=True)(inputs)

        # Transformer block
        transformer_output = self.transformer_block(x)

        # Additive Attention after Transformer
        query = Dense(self.lstm_units)(transformer_output)
        key = Dense(self.lstm_units)(transformer_output)
        value = transformer_output
        attention_output = self.additive_attention(query, key, value)

        # Second LSTM layer
        x = LSTM(self.lstm_units)(attention_output)

        # Dense layers for classification
        x = Dense(128, activation='relu')(x)
        x = Dropout(self.dropout_rate)(x)
        x = Dense(num_classes, activation='softmax')(x)

        model = Model(inputs, x)
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )

        return model

    def fit(self, X, y, epochs=50, batch_size=32, validation_split=0.2, class_balance=True):
        """
        Fit the model to the data

        Parameters:
        -----------
        X : array-like
            Feature matrix
        y : array-like
            Target vector
        epochs : int
            Number of training epochs
        batch_size : int
            Batch size for training
        validation_split : float
            Proportion of data to use for validation
        class_balance : bool
            Whether to balance classes using oversampling

        Returns:
        --------
        self : object
            Returns self
        """
        # Encode the target variable
        y_encoded = self.label_encoder.fit_transform(y)

        # Balance the dataset using oversampling if requested
        if class_balance:
            oversampler = RandomOverSampler(random_state=self.random_state)
            X_resampled, y_resampled = oversampler.fit_resample(X, y_encoded)
        else:
            X_resampled, y_resampled = X, y_encoded

        # Split into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(
            X_resampled, y_resampled,
            test_size=validation_split,
            random_state=self.random_state,
            shuffle=True
        )

        # Scale the features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Apply PCA for dimensionality reduction
        X_train_pca, X_test_pca = self.apply_pca(X_train_scaled, X_test_scaled)

        # Apply Squeeze-and-Excitation block after PCA
        X_train_se = self.squeeze_and_excitation(X_train_pca)
        X_test_se = self.squeeze_and_excitation(X_test_pca)

        # Reshape the data for LSTM with Transformers (samples, timesteps, features)
        X_train_lstm = X_train_se[..., np.newaxis]
        X_test_lstm = X_test_se[..., np.newaxis]

        # Convert labels to categorical
        num_classes = len(np.unique(y_resampled))
        y_train_categorical = np.eye(num_classes)[y_train]
        y_test_categorical = np.eye(num_classes)[y_test]

        # Build the model if not already built
        if self.model is None:
            self.model = self.build_model(
                input_shape=(X_train_lstm.shape[1], X_train_lstm.shape[2]),
                num_classes=num_classes
            )

        # Train the model
        self.history = self.model.fit(
            X_train_lstm, y_train_categorical,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(X_test_lstm, y_test_categorical)
        )

        return self

    def predict(self, X):
        """
        Make predictions with the trained model

        Parameters:
        -----------
        X : array-like
            Feature matrix

        Returns:
        --------
        y_pred : array
            Predicted class labels
        """
        if self.model is None:
            raise ValueError("Model has not been trained yet. Call fit() first.")

        # Scale the features
        X_scaled = self.scaler.transform(X)

        # Apply PCA
        X_pca = self.pca.transform(X_scaled)

        # Apply Squeeze-and-Excitation
        X_se = self.squeeze_and_excitation(X_pca)

        # Reshape for LSTM
        X_lstm = X_se[..., np.newaxis]

        # Get predicted probabilities
        y_pred_proba = self.model.predict(X_lstm)

        # Convert to class indices
        y_pred_indices = np.argmax(y_pred_proba, axis=1)

        # Convert back to original labels
        y_pred = self.label_encoder.inverse_transform(y_pred_indices)

        return y_pred

    def evaluate(self, X, y):
        """
        Evaluate the model on test data

        Parameters:
        -----------
        X : array-like
            Feature matrix
        y : array-like
            True class labels

        Returns:
        --------
        metrics : dict
            Dictionary of evaluation metrics
        """
        # Get predictions
        y_pred = self.predict(X)

        # Encode true labels
        y_encoded = self.label_encoder.transform(y)

        # Calculate confusion matrix
        cm = confusion_matrix(y_encoded, self.label_encoder.transform(y_pred))

        # Calculate classification report
        report = classification_report(y, y_pred, output_dict=True)

        # Return metrics
        return {
            'accuracy': report['accuracy'],
            'confusion_matrix': cm,
            'classification_report': report
        }

    def plot_training_history(self):
        """
        Plot the training history

        Returns:
        --------
        fig : matplotlib figure
            Figure with training history plots
        """
        if self.history is None:
            raise ValueError("Model has not been trained yet. Call fit() first.")

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

        # Plot accuracy
        ax1.plot(self.history.history['accuracy'])
        ax1.plot(self.history.history['val_accuracy'])
        ax1.set_title('Model Accuracy')
        ax1.set_ylabel('Accuracy')
        ax1.set_xlabel('Epoch')
        ax1.legend(['Train', 'Validation'], loc='upper left')

        # Plot loss
        ax2.plot(self.history.history['loss'])
        ax2.plot(self.history.history['val_loss'])
        ax2.set_title('Model Loss')
        ax2.set_ylabel('Loss')
        ax2.set_xlabel('Epoch')
        ax2.legend(['Train', 'Validation'], loc='upper left')

        plt.tight_layout()
        return fig

    def plot_confusion_matrix(self, X, y):
        """
        Plot the confusion matrix

        Parameters:
        -----------
        X : array-like
            Feature matrix
        y : array-like
            True class labels

        Returns:
        --------
        fig : matplotlib figure
            Figure with confusion matrix plot
        """
        # Get predictions
        y_pred = self.predict(X)

        # Calculate confusion matrix
        cm = confusion_matrix(y, y_pred)

        # Plot
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax)
        ax.set_title('Confusion Matrix')
        ax.set_ylabel('True Label')
        ax.set_xlabel('Predicted Label')

        return fig

# Usage example:
"""
# Load your dataset
dataset = pd.read_csv('your_dataset.csv')

# Initialize the model
model = HybridLSTMTransformerModel(
    n_components=20,
    lstm_units=64,
    num_heads=4,
    ff_dim=128,
    dropout_rate=0.2
)

# Split features and target
X = dataset.drop(columns=['class'])
y = dataset['class']

# Fit the model
model.fit(X, y, epochs=50, batch_size=32)

# Make predictions
predictions = model.predict(X_test)

# Evaluate the model
metrics = model.evaluate(X_test, y_test)
print(f"Test Accuracy: {metrics['accuracy']:.4f}")

# Plot training history
model.plot_training_history()

# Plot confusion matrix
model.plot_confusion_matrix(X_test, y_test)
"""