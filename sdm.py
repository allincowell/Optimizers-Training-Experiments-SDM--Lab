# -*- coding: utf-8 -*-
"""sdm-ass2.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/12IeBO7nhAdn5Tk8RK8F5SCcUTJMqjzLO
"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install wandb

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torch.backends.cudnn as cudnn

import torchvision
import torchvision.transforms as transforms

import os
import argparse

# Extra imports
import itertools
import matplotlib.pyplot as plt
import copy
import numpy as np
from sklearn.metrics import confusion_matrix
import wandb

wandb.login()

device = 'cuda' if torch.cuda.is_available() else 'cpu'
best_acc = 0  # best test accuracy

# Data
print('Data transformation')
transform_train = transforms.Compose([
    transforms.RandomCrop(32, padding=4),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])

trainset = torchvision.datasets.CIFAR10(
    root='./data', train=True, download=True, transform=transform_train)
trainloader = torch.utils.data.DataLoader(
    trainset, batch_size=128, shuffle=True, num_workers=2)

testset = torchvision.datasets.CIFAR10(
    root='./data', train=False, download=True, transform=transform_test)
testloader = torch.utils.data.DataLoader(
    testset, batch_size=100, shuffle=False, num_workers=2)

classes = ('plane', 'car', 'bird', 'cat', 'deer',
           'dog', 'frog', 'horse', 'ship', 'truck')

#Model
print('Model creation')

#### net = Invoke pretrained ResNet18 model #######
net = torchvision.models.resnet18(pretrained = True)
net = net.to(device)

def print_and_log(avg_train_epoch_loss, avg_test_epoch_loss, avg_test_epoch_accuracy):
  print("Testing Loss = {:.5f}".format(avg_test_epoch_loss))
  print("Testing Accuracy = {:.5f}".format(avg_test_epoch_accuracy))
  wandb.log({"Training Loss": avg_train_epoch_loss, "Testing Loss": avg_test_epoch_loss, "Testing Accuracy": avg_test_epoch_accuracy})

# Training
def train_and_test(net, loss_criterion, optimizer, number_of_epochs = 4):
    best_model = copy.deepcopy(net.state_dict())
    best_acc = 0.0
    prev_test_epoch_loss = 2e18
    MAX_TIMES_MONOTONIC_LOSS = 2
    cur_times_monotonic_loss = 0

    for i in range(number_of_epochs):
      print("Epoch #{} of {}".format(i + 1, number_of_epochs))
      net.train()
      correctly_classified = 0
      sum_train_epoch_loss = 0.0

      for data, classification in trainloader:
        data = data.to(device)
        classification = classification.to(device)

        optimizer.zero_grad()
        with torch.set_grad_enabled(True):
          model_output_tensor = net(data)
          output_max, arg_max = torch.max(model_output_tensor, 1)
          cur_loss = loss_criterion(model_output_tensor, classification)
          cur_loss.backward()
          optimizer.step()
        
        correctly_classified += torch.sum(classification.data == arg_max)
        sum_train_epoch_loss += data.size(0) * cur_loss.item()
      
      SIZE = len(trainset)
      avg_train_epoch_accuracy = correctly_classified.double() / SIZE
      avg_train_epoch_loss = sum_train_epoch_loss / SIZE

      print("Training Loss = {:.5f}".format(avg_train_epoch_loss))
      print("Training Accuracy = {:.5f}".format(avg_train_epoch_accuracy))

      net.eval()
      correctly_classified = 0
      sum_test_epoch_loss = 0.0

      for data, classification in testloader:
        data = data.to(device)
        classification = classification.to(device)

        with torch.set_grad_enabled(False):
          model_output_tensor = net(data)
          output_max, arg_max = torch.max(model_output_tensor, 1)
          cur_loss = loss_criterion(model_output_tensor, classification)
        
        correctly_classified += torch.sum(classification.data == arg_max)
        sum_test_epoch_loss += data.size(0) * cur_loss.item()
      
      SIZE = len(testset)
      avg_test_epoch_accuracy = correctly_classified.double() / SIZE
      avg_test_epoch_loss = sum_test_epoch_loss / SIZE

      if avg_test_epoch_loss < prev_test_epoch_loss:
        cur_times_monotonic_loss = 0
      else:
        cur_times_monotonic_loss += 1
      
      prev_test_epoch_loss = avg_test_epoch_loss
      if cur_times_monotonic_loss > MAX_TIMES_MONOTONIC_LOSS:
        print("Early stopping")
        print_and_log(avg_train_epoch_loss, avg_test_epoch_loss, avg_test_epoch_accuracy)
        break
      
      if avg_test_epoch_accuracy > best_acc:
        best_model = copy.deepcopy(net.state_dict())
        best_acc = avg_test_epoch_accuracy
      
      print_and_log(avg_train_epoch_loss, avg_test_epoch_loss, avg_test_epoch_accuracy)
    
    net.load_state_dict(best_model)
    print("Best Accuracy = {:.5f}".format(best_acc))
    return net

def classify(net, loader):
  sample_images = []
  predicted_classifications = torch.tensor([]).to(device)

  for data, classification in loader:
    data = data.to(device)
    classification = classification.to(device)
    with torch.set_grad_enabled(False):
      model_output_tensor = net(data)
      prediction = model_output_tensor.max(1, keepdim = True)[1]
      predicted_classifications = torch.cat((predicted_classifications, model_output_tensor), dim = 0)
      sample_images.append(wandb.Image(data[0], caption = "Pred = {}, Truth = {}".format(classes[prediction[0].item()], classes[classification[0]])))
  
  wandb.log({"Sample Prediction Samples": sample_images})
  return predicted_classifications

# Prepare net to train all the layers
net = torchvision.models.resnet18(pretrained = True)

# Making the Fully connected layer
resnet18_input_features = net.fc.in_features
net.fc = nn.Linear(resnet18_input_features, len(classes))
net = net.to(device)

# All layers - SGD
run = wandb.init(project = "Ass2", name = "SGD-ALL-LAYERS")
config = wandb.config          # Initialize config
config.batch_size = 128         # input batch size for training
config.test_batch_size = 128    # input batch size for testing
config.epochs = 200             # number of epochs to train
config.lr = 0.001               # learning rate
config.momentum = 0.9
config.log_interval = 10     # how many batches to wait before logging training status

print("All layers - SGD")
wandb.watch(net)

optimizer = optim.SGD(net.parameters(), lr = config.lr, momentum = config.momentum)
loss_criterion = nn.CrossEntropyLoss()
sgd_all_best_model = train_and_test(net, loss_criterion, optimizer, 200)
sgd_all_predictions = classify(sgd_all_best_model.to(device), testloader)
run.finish()

# All layers - Adam
run = wandb.init(project = "Ass2", name = "ADAM-ALL-LAYERS")
config = wandb.config          # Initialize config
config.batch_size = 128         # input batch size for training
config.test_batch_size = 128    # input batch size for testing
config.epochs = 200             # number of epochs to train
config.lr = 0.01               # learning rate
config.log_interval = 10     # how many batches to wait before logging training status

print("All layers - ADAM")
wandb.watch(net)

optimizer = optim.Adam(net.parameters(), config.lr)
loss_criterion = nn.CrossEntropyLoss()
adam_all_best_model = train_and_test(net, loss_criterion, optimizer, 200)
adam_all_predictions = classify(adam_all_best_model.to(device), testloader)
run.finish()

# Prepare net to train the last layers
net = torchvision.models.resnet18(pretrained = True)
for param in net.parameters():
  param.requires_grad = False

resnet18_input_features = net.fc.in_features
net.fc = nn.Linear(resnet18_input_features, len(classes))
net = net.to(device)

# Single Layer SGD
run = wandb.init(project = "Ass2", name = "SGD-LAST-LAYER")
config = wandb.config          # Initialize config
config.batch_size = 128         # input batch size for training
config.test_batch_size = 128    # input batch size for testing
config.epochs = 4             # number of epochs to train
config.lr = 0.001               # learning rate
config.momentum = 0.9
config.log_interval = 10     # how many batches to wait before logging training status

print("SGD-LAST-LAYER")
wandb.watch(net)

optimizer = optim.SGD(net.parameters(), lr = config.lr, momentum = config.momentum)
loss_criterion = nn.CrossEntropyLoss()
sgd_last_best_model = train_and_test(net, loss_criterion, optimizer, 200)
sgd_last_predictions = classify(sgd_last_best_model.to(device), testloader)
run.finish()

# Single Layer Adam
run = wandb.init(project = "Ass2", name = "ADAM-LAST-LAYER")
config = wandb.config          # Initialize config
config.batch_size = 128         # input batch size for training
config.test_batch_size = 128    # input batch size for testing
config.epochs = 200             # number of epochs to train
config.lr = 0.01               # learning rate
config.log_interval = 10     # how many batches to wait before logging training status

print("ADAM-LAST-LAYER")
wandb.watch(net)

optimizer = optim.Adam(net.parameters(), config.lr)
loss_criterion = nn.CrossEntropyLoss()
adam_last_best_model = train_and_test(net, loss_criterion, optimizer, 200)
adam_last_predictions = classify(adam_last_best_model.to(device), testloader)
run.finish()

# code for confusion matrix
from IPython.display import FileLink
def plot_confusion_matrix(matrix, classes, name):
  plt.figure(figsize=(10, 10))
  plt.imshow(matrix, interpolation = 'nearest', cmap = plt.cm.Reds)
  plt.title(name)
  plt.colorbar()
  tick_marks = np.arange(len(classes))
  plt.xticks(tick_marks, classes, rotation = 45)
  plt.yticks(tick_marks, classes)
  cutoff = matrix.max() / 2.
  for i, j in itertools.product(range(matrix.shape[0]), range(matrix.shape[1])):
    plt.text(j, i, format(matrix[i, j], "d"), horizontalalignment = "center", color = "white" if matrix[i, j] > cutoff else "black")
  plt.show()

confusion_matrix_sgd_last = confusion_matrix(testset.targets, sgd_last_predictions.argmax(dim = 1).cpu().clone().numpy())
confusion_matrix_adam_last = confusion_matrix(testset.targets, adam_last_predictions.argmax(dim = 1).cpu().clone().numpy())
confusion_matrix_sgd_full = confusion_matrix(testset.targets, sgd_all_predictions.argmax(dim = 1).cpu().clone().numpy())
confusion_matrix_adam_full = confusion_matrix(testset.targets, adam_all_predictions.argmax(dim = 1).cpu().clone().numpy())

plot_confusion_matrix(confusion_matrix_sgd_full, classes, "SGD - All layers")
plot_confusion_matrix(confusion_matrix_adam_full, classes, "Adam - All layers")
plot_confusion_matrix(confusion_matrix_sgd_last, classes, "SGD - Last layer")
plot_confusion_matrix(confusion_matrix_adam_last, classes, "Adam - Last layer")

