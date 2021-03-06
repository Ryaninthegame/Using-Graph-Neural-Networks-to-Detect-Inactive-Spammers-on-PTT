import argparse
import math
import os
import json
import time
import random
import torch
import dgl
import torch.nn as nn
import torch.optim as optim
import numpy as np
import scipy.sparse as sp
from dgl.nn import TAGConv

class net(nn.Module):
    def __init__(self, k, withSuspectValue):
        super(net, self).__init__()
        self.k = k
        self.relu = nn.LeakyReLU(0.1)
        if withSuspectValue:
            self.TAGConv_1 = TAGConv(73, 32, k=self.k)
        else:
            self.TAGConv_1 = TAGConv(72, 32, k=self.k)
        self.fc1 = nn.Linear(32, 16)
        self.fc2 = nn.Linear(16, 8)
        self.fc3 = nn.Linear(8, 4)
        self.fc4 = nn.Linear(4, 2)
        self.batchNorm_1 = nn.BatchNorm1d(32, affine=True)
        self.batchNorm_2 = nn.BatchNorm1d(16, affine=True)
        self.batchNorm_3 = nn.BatchNorm1d(8, affine=True)
        self.batchNorm_4 = nn.BatchNorm1d(4, affine=True)
        self.batchNorm_5 = nn.BatchNorm1d(2, affine=True)
        self.Softmax = nn.Softmax(dim=1)
        
    def forward(self, x, adj):
        x = self.TAGConv_1(adj, x)
        x = self.relu(self.batchNorm_1(x))
        x = self.fc1(x)
        x = self.relu(self.batchNorm_2(x))
        x = self.fc2(x)
        x = self.relu(self.batchNorm_3(x))
        x = self.fc3(x)
        x = self.relu(self.batchNorm_4(x))
        x = self.fc4(x)
        x = self.relu(self.batchNorm_5(x))
        x = self.Softmax(x)
        return x
    

def normalization(array):
    for i in range(len(array[0])):
        min_ = array[0][i].min()
        max_ = array[0][i].max()
        if(min_ == max_):
            continue
        for j in range(len(array[0][0])):
            array[0][i][j] = np.around((array[0][i][j]-min_)/(max_-min_), decimals=5)
    return array


def loadJson(path, file):
    f = open(path+file+".json", 'r')
    for line in f:
        jsonFile = json.loads(line)
    f.close()
    return jsonFile


def loadIndex(trainBoundary, testBoundary):
    trainIndex = torch.LongTensor(range(trainBoundary))
    testIndex = torch.LongTensor(range(trainBoundary, testBoundary))
    updateLossIndex = [i for i in range(trainBoundary)]  
    return trainIndex, testIndex, updateLossIndex


def getFeature(withSuspectValue):
    infoPath = './data/information/'
    numpyPath = './data/userSet/'
    userSet = loadJson(infoPath, 'userIndex')
    userLabel = loadJson(infoPath, 'userLabel')
    suspectValue = loadJson(infoPath, 'suspectValue')
    
    featureSet, label = [], []
    for user in userSet:
        suspect = suspectValue[user]
        if userLabel[user]==0:
            label.append(0)
        else:
            label.append(1)
        user = normalization(np.load(numpyPath+user+r'.npy')).reshape((72))
        if withSuspectValue:
            user = np.append(user, suspect)
        featureSet.append(user)
    return featureSet, label


def loadData(withSuspectValue):
    path = "./data/information/"
    adjacentMatrix = sp.load_npz(path+"adjacentMatrix.npz")
    adjacentMatrix = dgl.from_scipy(adjacentMatrix).to(_device)
    featureSet, label = getFeature(withSuspectValue)
    featureSet = torch.from_numpy(np.array(featureSet)).float().to(_device)
    label = torch.Tensor(label).long().to(_device)
    return adjacentMatrix, featureSet, label


def train(epoch, index, cutting, adjacentMatrix, feature, label, trainIndex):
    lossSet = []
    batch = int(len(trainIndex)/cutting)
    for i in range(epoch):
        for j in range(cutting):
            indexPerBatch = trainIndex[index[j*batch:(j+1)*batch]].to(_device)
            optimizer.zero_grad()
            output = model(feature, adjacentMatrix)
            loss = criterion(output[indexPerBatch], label[indexPerBatch])
            loss.backward()
            optimizer.step()
        lossSet.append(loss.item())
    return lossSet


if __name__ == "__main__":
    _parser = argparse.ArgumentParser()
    _parser.add_argument("--withSuspectValue", 
                         default = True,
                         help = "Use Suspect Value", 
                        type=bool)
    _parser.add_argument("--cutting",
                         default = 3,
                         help = "Batch = dataNum/cutting", 
                        type=int)
    _parser.add_argument("--epoch",
                         default = 5000,
                         help = "Epoch", 
                        type=int)
    _parser.add_argument("--K", 
                         default = 3,
                         help = "TAGCN K", 
                        type=int)
    _args = _parser.parse_args()
    
    _withSuspectValue, _cutting, _epoch, _k = _args.withSuspectValue, _args.cutting, _args.epoch, _args.K
    
    if torch.cuda.is_available():
        _device = torch.device("cuda:0")
        print("Use cuda")
    else:
        _device = torch.device("cpu")
        print("Can't find cuda, use cpu")
    
    _adjacentMatrix, _featureSet, _label = loadData(_withSuspectValue)
    _trainIndex, _testIndex, _updateLossIndex = loadIndex(35681, 44602)
    
    _startTime = time.time()
    _savePath = './TAGCN.pth'
    model = net(_k, _withSuspectValue)
    model.to(_device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    _lossSet = train(_epoch, _updateLossIndex, _cutting, _adjacentMatrix, _featureSet, _label, _trainIndex)

    torch.save(model, _savePath)
    _endTime = time.time()
    print("Time :", round(_endTime-_startTime), "(s)  done")
