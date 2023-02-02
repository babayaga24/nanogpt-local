import torch
import torch.nn as nn
from torch.nn import functional as F

# hyperparameters
batch_size = 32 #the number of independent sequences we will process in parallel
block_size = 8 #the maximum context length for predictions
max_iters = 3000
eval_internal = 300
learning_rate = 1e-2
device = 'cuda' if torch.cuda.is_available() else 'cpu'
eval_iters = 200
# -------------

torch.manual_seed(1337)

# Dataset to train on
!wget https://raw.githubusercontent.com/babayaga24/nanoGPT/master/merged_text1.txt

#read it in to inspect it
with open('merged_text1.txt', 'r', encoding='utf-8') as f:
    text = f.read()

print("Length of dataset in characters: ", len(text))

#look at first 1000 characters
print(text[:1000])

# All the unique characters that occur in this text
chars = sorted(list(set(text)))
vocab_size = len(chars)
print(''.join(chars))
print(vocab_size)

# Create mapping from characters to integers
stoi = { ch:i for i,ch in enumerate(chars) }
itos = { i:ch for i,ch in enumerate(chars) }
encode = lambda s: [stoi[c] for c in s] # take a string and output a list of integers
decode = lambda l: ''.join([itos[i] for i in l]) # take a list of integers and output a string


#Encode the entire dataset and store it into a torch.tensor

data = torch.tensor(encode(text), dtype=torch.long)

#Let's split up the data into train and validation sets
n = int(0.9*len(data)) #first 90% will be training and the rest validation
train_data = data[:n]
val_data = data[n:]

# data loading
def get_batch(split):
  # generate a small batch of data of inputs x and targets y
  data = train_data if split == 'train' else val_data
  ix = torch.randint(len(data) - block_size, (batch_size,))
  x = torch.stack([data[i:i+block_size] for i in ix])
  y = torch.stack([data[i+1:i+block_size+1]for i in ix])
  return x, y

@torch.no_grad()
def estimate_loss():
  out = {}
  model.eval()
  for split in ['train', 'val']:
    losses = torch.zeros(eval_iters)
    for k in range(eval_iters):
      X, Y = get_batch(split)
      logits, loss = model(X, Y)
      losses[k] = loss.item()
    out[split] = losses.mean()
  model.train()
  return out

# Simple Bigram model
class BigramLanguageModel(nn.Module):

    def __init__(self, vocab_size):
      super().__init__()
      #each token directly reads off the logits for the next token from the lookup table
      self.token_embedding_table = nn.Embedding(vocab_size, vocab_size)
    
    def forward(self, idx, targets=None):
        #idx and targets are both (B,T) tensor of integers
        logits = self.token_embedding_table(idx) #(B,T,C)

        if targets is None:
          loss = None
        else:
          B, T, C = logits.shape
          logits = logits.view(B*T, C)
          targets = targets.view(B*T)      
          loss = F.cross_entropy(logits, targets)

        return logits, loss

    def generate(self, idx, max_new_tokens):
      #idx is (B, T) array of indices in the current context
        for _ in range(max_new_tokens):
          # get the predictions
          logits, loss = self(idx)
          # focus only on the last time step
          logits = logits[:, -1, :] # becomes (B, C)
          # apply softmax to get probabilities
          probs = F.softmax(logits, dim=-1) # (B, C)
          # sample from the distribution
          idx_next = torch.multinomial(probs, num_samples=1) # (B,1)
          # append sampled index to the running sequence
          idx = torch.cat((idx, idx_next), dim=1) # (B, T+1)
        return idx

model = BigramLanguageModel(vocab_size)
m = model.to(device)

# create a Pytorch optimizer
optimizer = torch.optim.AdamW(m.parameters(), lr=1e-3)

for iter in range(max_iters):

    # every once in a while evaluate the loss on train and val sets
    if iter % eval_interval == 0:
      losses = estimate_loss()
      print(f"step {iter}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}")

    # sample a batch of data
    xb, yb = get_batch('train')

    #evaluate the loss
    logits, loss = m(xb, yb)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()

# generate from the model
context = torch.zeros((1,1), dtype=torch.long, device=device)
print (decode(m.generate(torch.zeros((1, 1), dtype=torch.long), max_new_tokens=400)[0].tolist()))