import random
import numpy as np


class ReplayBuffer(object):
    def __init__(self, size):
        """Create Replay buffer.
        Parameters
        ----------
        size: int
            Max number of transitions to store in the buffer. When the buffer
            overflows the old memories are dropped.
        """
        self._storage = []
        self._maxsize = size
        self._next_idx = 0

    def __len__(self):
        return len(self._storage)

    def add(self, obs_t, action, reward, obs_tp1, done):
        data = (obs_t, action, reward, obs_tp1, done)

        if self._next_idx >= len(self._storage):
            self._storage.append(data)
        else:
            self._storage[self._next_idx] = data
        self._next_idx = (self._next_idx + 1) % self._maxsize

    def _encode_sample(self, idxes):
        obses_t, actions, rewards, obses_tp1, dones = [], [], [], [], []
        for i in idxes:
            data = self._storage[i]
            obs_t, action, reward, obs_tp1, done = data
            obses_t.append(np.array(obs_t, copy=False))
            actions.append(np.array(action, copy=False))
            rewards.append(reward)
            obses_tp1.append(np.array(obs_tp1, copy=False))
            dones.append(done)
        return (
            np.array(obses_t),
            np.array(actions),
            np.array(rewards),
            np.array(obses_tp1),
            np.array(dones)
        )

    def sample(self, batch_size):
        """Sample a batch of experiences.
        Parameters
        ----------
        batch_size: int
            How many transitions to sample.
        Returns
        -------
        obs_batch: np.array
            batch of observations
        act_batch: np.array
            batch of actions executed given obs_batch
        rew_batch: np.array
            rewards received as results of executing act_batch
        next_obs_batch: np.array
            next set of observations seen after executing act_batch
        done_mask: np.array
            done_mask[i] = 1 if executing act_batch[i] resulted in
            the end of an episode and 0 otherwise.
        """
        idxes = [
            random.randint(0, len(self._storage) - 1)
            for _ in range(batch_size)
        ]
        return self._encode_sample(idxes)


class PrioritizedReplayBuffer(object):
    """Fixed-size buffer to store experience tuples."""

    def __init__(self, buffer_size, batch_size=64, seed=5,
                 compute_weights=True, alpha=0.5, beta=0.5):
        """Initialize a ReplayBuffer object.
        Params
        ======
            buffer_size (int): maximum size of buffer
            experiences_per_sampling (int): number of experiences to sample during a sampling iteration
            batch_size (int): size of each training batch
            seed (int): random seed
        """
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.alpha = alpha
        self.alpha_decay_rate = 0.99
        self.beta = beta
        self.beta_growth_rate = 1.001
        random.seed(seed)
        self.compute_weights = compute_weights
        self.experience_count = 0

        self.experience = np.zeros(shape=(self.buffer_size, 5), dtype='object')
        self.data = np.zeros(shape=(self.buffer_size, 4), dtype='object')

        self.sampled_batches = []
        self.current_batch = 0
        self.priorities_sum_alpha = 0
        self.priorities_max = 1
        self.weights_max = 1

    def update_priorities(self, tds, indices):
        for td, index in zip(tds, indices):
            N = min(self.experience_count, self.buffer_size)

            updated_priority = td
            if updated_priority > self.priorities_max:
                self.priorities_max = updated_priority

            if self.compute_weights:
                updated_weight = ((N * updated_priority) ** (-self.beta)) / self.weights_max
                if updated_weight > self.weights_max:
                    self.weights_max = updated_weight
            else:
                updated_weight = 1

            old_priority = self.data[index, 0]
            self.priorities_sum_alpha += updated_priority ** self.alpha - old_priority ** self.alpha
            updated_probability = updated_priority ** self.alpha / self.priorities_sum_alpha
            self.data[index] = [updated_priority, updated_probability, updated_weight, index]

    def _encode_samples(self):
        """Randomly sample a batch of experiences from memory."""
        return np.array(random.choices(self.data,
                                       self.data[:, 1],
                                       k=self.batch_size))

    def update_parameters(self):
        self.alpha *= self.alpha_decay_rate
        self.beta *= self.beta_growth_rate
        if self.beta > 1:
            self.beta = 1
        N = min(self.experience_count, self.buffer_size)
        self.priorities_sum_alpha = np.sum(self.data[:, 0] ** self.alpha)
        for element in self.data:
            probability = element[0] ** self.alpha / self.priorities_sum_alpha
            weight = 1
            if self.compute_weights:
                weight = ((N * element[1]) ** (-self.beta)) / self.weights_max
            self.data[int(element[-1]), :] = [element[0], probability, weight, element[-1]]

    def add(self, state, action, reward, next_state, done):
        """Add a new experience to memory."""
        self.experience_count += 1
        index = self.experience_count % self.buffer_size

        if self.experience_count > self.buffer_size:
            temp = self.data[index]
            self.priorities_sum_alpha -= temp[0] ** self.alpha
            if temp[0] == self.priorities_max:
                self.data[index, 0] = 0
                self.priorities_max = max(self.data, key=lambda x: x[0])[0]
            if self.compute_weights:
                if temp[2] == self.weights_max:
                    self.data[index, 2] = 0
                    self.weights_max = max(self.data, key=lambda x: x[2])[2]
            self.experience_count = self.buffer_size

        priority = self.priorities_max
        weight = self.weights_max
        self.priorities_sum_alpha += priority ** self.alpha
        probability = priority ** self.alpha / self.priorities_sum_alpha
        self.experience[index] = np.array([state, action, reward, next_state, done], dtype='object')
        self.data[index] = np.array([priority, probability, weight, index], dtype='object')

    def sample(self):
        sampled_batch = self._encode_samples()

        weights = np.copy(sampled_batch[:, 2]).astype(float)
        idx = np.copy(sampled_batch[:, -1]).astype(int)

        states = np.stack(self.experience[idx, 0])
        actions = np.stack(self.experience[idx, 1])
        rewards = np.stack(self.experience[idx, 2])
        next_states = np.stack(self.experience[idx, 3])
        dones = np.stack(self.experience[idx, 4])

        return states, actions, rewards, next_states, dones, np.array(weights), idx

    def __len__(self):
        """Return the current size of internal memory."""
        return self.experience_count
