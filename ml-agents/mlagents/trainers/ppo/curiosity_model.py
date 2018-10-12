import tensorflow as tf
from ..models import LearningModel


class ICM(object):
    def __init__(self, policy_model, strength=0.01, encoding_size=128):
        self.encoding_size = encoding_size
        self.strength = strength
        self.policy_model = policy_model
        encoded_state, encoded_next_state = self.create_curiosity_encoders()
        self.create_inverse_model(encoded_state, encoded_next_state)
        self.create_forward_model(encoded_state, encoded_next_state)

    def create_curiosity_encoders(self):
        """
        Creates state encoders for current and future observations.
        Used for implementation of ﻿Curiosity-driven Exploration by Self-supervised Prediction
        See https://arxiv.org/abs/1705.05363 for more details.
        :return: current and future state encoder tensors.
        """
        encoded_state_list = []
        encoded_next_state_list = []

        if self.policy_model.vis_obs_size > 0:
            self.next_visual_in = []
            visual_encoders = []
            next_visual_encoders = []
            for i in range(self.policy_model.vis_obs_size):
                # Create input ops for next (t+1) visual observations.
                next_visual_input = self.policy_model.create_visual_input(
                    self.policy_model.brain.camera_resolutions[i],
                    name="next_visual_observation_" + str(
                        i))
                self.next_visual_in.append(next_visual_input)

                # Create the encoder ops for current and next visual input.
                # Note that these encoders are siamese.
                encoded_visual = self.policy_model.create_visual_observation_encoder(
                    self.policy_model.visual_in[i],
                    self.policy_model.curiosity_enc_size,
                    LearningModel.swish, 1,
                    "stream_{}_visual_obs_encoder"
                    .format(i), False)

                encoded_next_visual = self.policy_model.create_visual_observation_encoder(
                    self.next_visual_in[i],
                    self.encoding_size,
                    LearningModel.swish, 1,
                    "stream_{}_visual_obs_encoder".format(i),
                    True)
                visual_encoders.append(encoded_visual)
                next_visual_encoders.append(encoded_next_visual)

            hidden_visual = tf.concat(visual_encoders, axis=1)
            hidden_next_visual = tf.concat(next_visual_encoders, axis=1)
            encoded_state_list.append(hidden_visual)
            encoded_next_state_list.append(hidden_next_visual)

        if self.policy_model.vec_obs_size > 0:
            # Create the encoder ops for current and next vector input.
            # Note that these encoders are siamese.
            # Create input op for next (t+1) vector observation.
            self.next_vector_in = tf.placeholder(shape=[None, self.policy_model.vec_obs_size],
                                                 dtype=tf.float32,
                                                 name='next_vector_observation')

            encoded_vector_obs = self.policy_model.create_vector_observation_encoder(
                self.policy_model.vector_in,
                self.encoding_size,
                LearningModel.swish, 2,
                "vector_obs_encoder",
                False)
            encoded_next_vector_obs = self.policy_model.create_vector_observation_encoder(
                self.next_vector_in,
                self.encoding_size,
                LearningModel.swish, 2,
                "vector_obs_encoder",
                True)
            encoded_state_list.append(encoded_vector_obs)
            encoded_next_state_list.append(encoded_next_vector_obs)

        encoded_state = tf.concat(encoded_state_list, axis=1)
        encoded_next_state = tf.concat(encoded_next_state_list, axis=1)
        return encoded_state, encoded_next_state

    def create_inverse_model(self, encoded_state, encoded_next_state):
        """
        Creates inverse model TensorFlow ops for Curiosity module.
        Predicts action taken given current and future encoded states.
        :param encoded_state: Tensor corresponding to encoded current state.
        :param encoded_next_state: Tensor corresponding to encoded next state.
        """
        combined_input = tf.concat([encoded_state, encoded_next_state], axis=1)
        hidden = tf.layers.dense(combined_input, 256, activation=LearningModel.swish)
        if self.policy_model.brain.vector_action_space_type == "continuous":
            pred_action = tf.layers.dense(hidden, self.policy_model.act_size[0], activation=None)
            squared_difference = tf.reduce_sum(
                tf.squared_difference(pred_action, self.policy_model.selected_actions), axis=1)
            self.inverse_loss = tf.reduce_mean(
                tf.dynamic_partition(squared_difference, self.policy_model.mask, 2)[1])
        else:
            pred_action = tf.concat(
                [tf.layers.dense(hidden, self.policy_model.act_size[i], activation=tf.nn.softmax)
                 for i in range(len(self.policy_model.act_size))], axis=1)
            cross_entropy = tf.reduce_sum(
                -tf.log(pred_action + 1e-10) * self.policy_model.selected_actions,
                axis=1)
            self.inverse_loss = tf.reduce_mean(
                tf.dynamic_partition(cross_entropy, self.policy_model.mask, 2)[1])

    def create_forward_model(self, encoded_state, encoded_next_state):
        """
        Creates forward model TensorFlow ops for Curiosity module.
        Predicts encoded future state based on encoded current state and given action.
        :param encoded_state: Tensor corresponding to encoded current state.
        :param encoded_next_state: Tensor corresponding to encoded next state.
        """
        combined_input = tf.concat([encoded_state, self.policy_model.selected_actions], axis=1)
        hidden = tf.layers.dense(combined_input, 256, activation=LearningModel.swish)
        pred_next_state = tf.layers.dense(hidden, self.encoding_size * (
                self.policy_model.vis_obs_size + int(self.policy_model.vec_obs_size > 0)),
                                          activation=None)
        squared_difference = 0.5 * tf.reduce_sum(
            tf.squared_difference(pred_next_state, encoded_next_state), axis=1)
        self.intrinsic_reward = tf.clip_by_value(self.strength * squared_difference,
                                                 0, 1)
        self.forward_loss = tf.reduce_mean(
            tf.dynamic_partition(squared_difference, self.policy_model.mask, 2)[1])

    def create_loss(self):
        self.loss = 10 * (0.2 * self.forward_loss + 0.8 * self.inverse_loss)
        self.policy_model.loss += self.loss
