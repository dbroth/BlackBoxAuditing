from itertools import product
from collections import defaultdict

from AbstractRepairer import AbstractRepairer

from collections import defaultdict
from copy import deepcopy

import networkx as nx
import random
import math

class Repairer(AbstractRepairer):
  def repair(self, data_to_repair, repair_amount):
    col_ids = range(len(data_to_repair[0]))

    # Get column type information
    col_types = ["Y"]*len(col_ids)
    for i, col in enumerate(col_ids):
      if i in self.features_to_ignore:
        col_types[i] = "I"
      elif i == self.feature_to_repair:
        col_types[i] = "X"
      else:
        continue

    col_type_dict = {col_id: col_type for col_id, col_type in zip(col_ids, col_types)}
    Y_col_ids = filter(lambda x: col_type_dict[x] == "Y", col_ids)
    not_I_col_ids = filter(lambda x: col_type_dict[x] != "I", col_ids)

    # To prevent potential perils with user-provided column names, map them to safe column names
    safe_stratify_cols = [self.feature_to_repair]

    # Extract column values for each attribute in data
    # Begin by initializing keys and values in dictionary
    data_dict = {col_id: [] for col_id in col_ids}
    
    # Populate each attribute with its column values
    for row in data_to_repair:
      for i in col_ids:
        data_dict[i].append(row[i])


    # Create unique value structures:
    # When performing repairs, we choose median values. If repair is partial, then values will
    # be modified to some intermediate value between the original and the median value. However,
    # the partially repaired value will only be chosen out of values that exist in the data set.
    # This prevents choosing values that might not make any sense in the data's context.
    # To do this, for each column, we need to sort all unique values and create two data structures:
    # a list of values, and a dict mapping values to their positions in that list. Example:
    #   There are unique_col_vals[col] = [1, 2, 5, 7, 10, 14, 20] in the column. A value 2 must be
    #   repaired to 14, but the user requests that data only be repaired by 50%. We do this by
    #   finding the value at the right index:
    #   index_lookup[col][2] = 1; index_lookup[col][14] = 5; this tells us that
    #   unique_col_vals[col][3] = 7 is 50% of the way from 2 to 14.
    unique_col_vals = {}
    index_lookup = {}
    for col_id in not_I_col_ids:
      col_values = data_dict[col_id] #TODO: Make this use all_data
      # extract unique values from column and sort
      col_values = sorted(list(set(col_values)))
      unique_col_vals[col_id] = col_values
      # look up a value, get its position
      index_lookup[col_id] = {col_values[i]: i for i in range(len(col_values))}


    # Make a list of unique values per each stratified column.
    # Then make a list of combinations of stratified groups. Example: race and gender cols are stratified:
    # [(white, female), (white, male), (black, female), (black, male)]
    # The combinations are tuples because they can be hashed and used as dictionary keys.
    # From these, find the sizes of these groups.
    unique_stratify_values = [unique_col_vals[i] for i in safe_stratify_cols]
    all_stratified_groups = list(product(*unique_stratify_values))
    # look up a stratified group, and get a list of indices corresponding to that group in the data
    stratified_group_indices = defaultdict(list)
    # Find the sizes of each combination of stratified groups in the data
    sizes = {group: 0 for group in all_stratified_groups}
    for i in range(len(data_dict[safe_stratify_cols[0]])):
      group = tuple(data_dict[col][i] for col in safe_stratify_cols)
      stratified_group_indices[group].append(i)
      sizes[group] += 1

    # Don't consider groups not present in data (size 0)
    all_stratified_groups = filter(lambda x: sizes[x], all_stratified_groups)

    # Separate data by stratified group to perform repair on each Y column's values given that their
    # corresponding protected attribute is a particular stratified group. We need to keep track of each Y column's
    # values corresponding to each particular stratified group, as well as each value's index, so that when we
    # repair the data, we can modify the correct value in the original data. Example: Supposing there is a
    # Y column, "Score1", in which the 3rd and 5th scores, 70 and 90 respectively, belonged to black women,
    # the data structure would look like: {("Black", "Woman"): {Score1: [(70,2),(90,4)]}}
    stratified_group_data = {group: {} for group in all_stratified_groups}
    for group in all_stratified_groups:
      for col_id in data_dict:
        stratified_col_values = sorted([(data_dict[col_id][i], i) for i in stratified_group_indices[group]], key=lambda vals: vals[0])
        stratified_group_data[group][col_id] = stratified_col_values
    features = {}
    categories = {}
    categories_count = {}
    desired_categories_count = {}
    group_size = {}
    categories_count_norm = {}
    print data_dict 
    for col_id in data_dict:
      if col_id in Y_col_ids:
        #data_dict[col_id] should be a list containing the values for all observations
        values = data_dict[col_id]
        feature = Feature(values, True)
        feature.categorize()
        bin_index_dict = feature.bin_index_dict
        print feature.bin_data
        print bin_index_dict
        categories[col_id] = []
        for key,value in bin_index_dict.items():
           categories[col_id].append(key)
        print categories
    for col_id in data_dict:
      if col_id in Y_col_ids:
        group_size[col_id] = {}
        features[col_id] = {}
        for group in all_stratified_groups:
          #values is a list like: [('A',0),('A',1),('B',2),('B',3),('B',4)], where the second element in the tuple is the index of the observation
          tuple_values = stratified_group_data[group][col_id]
          values=[]
          for tuple_value in tuple_values:
            values.append(tuple_value[0]) 
          feature = Feature(values, True)
          feature.categorize()
          print "Group " + str(group) + " has the following category counts: " + str(feature.category_count)
          group_size[col_id][group] = len(feature.data)
          features[col_id][group] = feature
    for col_id in data_dict:
      if col_id in Y_col_ids:
        categories_count[col_id]={category: [] for category in categories[col_id]}
        for group in all_stratified_groups:
          category_count = features[col_id][group].category_count
          for category in categories[col_id]:
            if category in category_count:
              count=category_count[category]
              categories_count[col_id][category].append(count)
            else:
              categories_count[col_id][category].append(0)

    for col_id in data_dict:
      if col_id in Y_col_ids:
        categories_count_norm[col_id] = {}
        for category in categories[col_id]:
          categories_count_norm[col_id][category]=[0]*len(categories_count[col_id][category])
          for i in range(len(categories_count[col_id][category])):
            print group_size
            print all_stratified_groups
            print categories_count[col_id][category]
            group= all_stratified_groups[i]
            orig_count = categories_count[col_id][category][i] 
            categories_count_norm[col_id][category][i] = orig_count* (1.0/group_size[col_id][group])
        print categories_count_norm
        categories_count[col_id]={category: [] for category in categories[col_id]}
        desired_categories_count[col_id]={}
        median = {}
        for category in categories[col_id]:
          median[category] = sorted(categories_count_norm[col_id][category])[len(categories_count_norm[col_id][category])/2]
        for i in range(len(all_stratified_groups)):
          group = all_stratified_groups[i]
          desired_categories_count[col_id][group] = {}
          for category in categories[col_id]:
            med=median[category]
            size = group_size[col_id][group] 
            temp=(1 - repair_amount)*categories_count_norm[col_id][category][i] + repair_amount*med
            estimate = math.floor(temp*(1.0*size))
            desired_categories_count[col_id][group][category] = estimate 
            print desired_categories_count

        total_overflow=0
        total_overflows={}
        for group in all_stratified_groups:
          feature = features[col_id][group]
          feature.desired_category_count = desired_categories_count[col_id][group]
          print "\nMax Flow on group: " + str(group)
          print feature.desired_category_count
          DG=create_graph(feature)
          [new_feature,overflow] = repair_feature(feature,DG)
          total_overflow += overflow
          total_overflows[group] = overflow
          features[col_id][group] = new_feature
        print "\nTotal overflow: " + str(total_overflow)
        
        assigned_overflow = {}
        distribution = {}
        for i in range(len(all_stratified_groups)):
          group = all_stratified_groups[i]
          distribution[group] = {}
          for j in range(len(categories[col_id])):
            category = categories[col_id][j]
            print categories_count_norm[col_id][category]
            distribution[group][j] = categories_count_norm[col_id][category][i]
        for group in all_stratified_groups:
          assigned_overflow[group] = {}
          for i in range(int(total_overflows[group])):
            dist = distribution[group]
            number = random.uniform(0, 1)
            print number
            cat_index = 0
            tally = 0
            for j in range(len(dist)):
              value=dist[j]
              if number < (tally+value):
                cat_index = j
                break
              tally += value
            assigned_overflow[group][i] = categories[col_id][cat_index]
            print "\nThis observation in group "+str(group) + " got assigned to category " + str(assigned_overflow[group][i]) + " facing probabilities " + str(dist)
        #Actually do the assignment
          count = 0
          for i in range(len(features[col_id][group].data)):
            value = (features[col_id][group].data)[i]
            if value ==0:
              (features[col_id][group].data)[i] = assigned_overflow[group][count]
              count += 1
        #Now we need to return our repaired feature in the form of our original dataset!! 
        for group in all_stratified_groups:
          indices = stratified_group_indices[group]
          count =0
          for index in indices:
            value = (features[col_id][group].data)[count]
            count += 1
            data_to_repair[index][col_id] = value
    return data_to_repair
        




class Feature:
  def __init__(self, data, categorical=False, name="no_name"):
    #data is an array of the data, with length n (# of observations)
    self.data = data
    #categorical is binary, True if categorical data 
    self.categorical = categorical
    #name of the feature column
    self.name = name
    #The following are initialized in categorize()
    #number of bins (number of categories)
    self.num_bins = None
    #bin_index_dict is type defaultdict(int), KEY: category, VALUE: category index
    self.bin_index_dict = None
    #bin_index_dict_reverse is type defaultdict(int), KEY: category index, VALUE: category 
    self.bin_index_dict_reverse = None
    #bin data is type defaultdict(int), Key: category index, VALUE: number of observations with that category
    self.bin_data = None
    #bin full data is type defaultdict(list), Key: category index, VALUE: array of indices i, where data[i] is in that category
    
    self.bin_fulldata = None
    #The following are initialized in repair()
    #bin_data_repaired is type defaultdict(int), Key: category index, VALUE: number of desired observations with that category 
    self.bin_data_repaired = None
    self.desired_category_count = None

    self.category_count=None
    
  def categorize(self):
    if self.categorical: 
      d1=defaultdict(int) #bin_data
      d2=defaultdict(int) #bin_index_dict
      d3=defaultdict(list) #bin_fulldata
      d4=defaultdict(int) #bin_index_dict_reverse
      d5=defaultdict(int) #category_count
      n = len(self.data)
      count = 0
      for i in range(0,n):
        obs = self.data[i]
        if obs in d2: pass  # if obs (i.e. category) is alreay a KEY in bin_index_data then don't do anything
        else:
          d2[obs] = count #bin_index_dict inits the KEY: category, with VALUE: count
          d4[count] = obs #bin_index_dict_reverse does the opposite
          count += 1
        bin_idx = d2[obs]
        d1[bin_idx] += 1 #add 1 to the obs category idex in bin_data
        d5[obs] += 1 #add 1 to the obs category NAME in category_count
        d3[bin_idx].append(i) #add obs to the list of obs with that category in bin_fulldata
      self.bin_data = d1 
      self.category_count = d5 
      self.num_bins = len(d1.items())
      self.bin_fulldata = d3
      self.bin_index_dict = d2
      self.bin_index_dict_reverse = d4
    else:
      print "error: not categorical data"

  def repair(self, repaird_data={}, protected_attribute =[]): #We have to make a design choice here (discussion in README)
    if (not self.bin_data): self.categorize() #checks to make the feature has run through categorize()
    else:
      d = deepcopy(self.bin_data) #deepcopy ensures that self.bin_data does not get mutated
      sumvals=0
      for key, value in d.items(): #we get the number of observations
        sumvals += value
      avgval = sumvals/len(d.items()) #divide number of observations by number of categorues
      remainder = sumvals % len(d.items()) 
      for key, value in d.items(): #evenly distribute the number of observations across categories
        if remainder > 0:
          d[key] = avgval +1
          remainder -= 1
        else:
          d[key] = avgval   
      self.bin_data_repaired = d #This is our temporary desired distribution (number of observation in each category)

def create_graph(feature): #creates graph given a Feature object
  DG=nx.DiGraph() #using networkx package
  bin_list = feature.bin_data.items()  
  bin_index_dict_reverse = feature.bin_index_dict_reverse
  desired_category_count = feature.desired_category_count
  k = feature.num_bins
  DG.add_node('s')
  DG.add_node('t')
  for i in range(0, k): #lefthand side nodes have capacity = number of observations in category i
    DG.add_node(i)
    DG.add_edge('s', i, {'capacity' : bin_list[i][1], 'weight' : 0})
  for i in range(k, 2*k): #righthand side nodes have capacity = DESIRED number of observations in category i
    DG.add_node(i)
    cat = bin_index_dict_reverse[i-k]
    DG.add_edge(i, 't', {'capacity' : desired_category_count[cat], 'weight' : 0})
  #Add special node to hold overflow
  DG.add_node(2*k)
  DG.add_edge(2*k, 't', {'weight' : 0})
  for i in range(0, k):
    for j in range(k,2*k): #for each edge from a lefthand side node to a righhand side node:
      if (i+k)==j:  #IF they represent the same category, the edge weight is 0
        DG.add_edge(i, j, {'weight' : 0})
      else: #IF they represent different categories, the edge weight is 1
        DG.add_edge(i, j, {'weight' : 1})
    #THIS IS THE OVERFLOW NODE!!
    DG.add_edge(i, 2*k, {'weight' : 2})
  return DG

def repair_feature(feature, DG): #new_feature = repair_feature(feature, create_graph(feature))
  mincostFlow = nx.max_flow_min_cost(DG, 's', 't') #max_flow_min_cost returns Dictionary of dictionaries. Keyed by nodes such that mincostFlow[u][v] is the flow edge (u,v)
  bin_dict = feature.bin_fulldata
  index_dict = feature.bin_index_dict_reverse
  size_data = len(feature.data)
  repair_bin_dict = {} 
  repair_data = [0]*size_data #initialize repaired data to be 0. If there are zero's after we fill it in the those observations belong in the overflow, "no category"
  k = feature.num_bins
  overflow = 0
  for i in range(0,k): #for each lefthand side node i
    overflow += mincostFlow[i][2*k]
    for j in range(k, 2*k): #for each righthand side node j
      edgeflow = mincostFlow[i][j] #get the int (edgeflow) representing the amount of observations going from node i to j
      print "Flow from " + str(i) +" to " + str(j-k) + " of " + str(edgeflow)
      group = random.sample(bin_dict[i], int(edgeflow)) #randomly sample x (edgeflow) unique elements from the list of observations in that category. 
      q=j-k #q is the category index for a righhand side node
      for elem in group: #for each element in the randomly selected group list
        bin_dict[i].remove(elem) #remove the element from the list of observation in that category
        repair_data[elem] = index_dict[q] #Mutate repair data at the index of the observation (elem) with its new category (it was 0) which is the category index for the righthand side node it flows to
      if q in repair_bin_dict: #if the category index is already keyed
        repair_bin_dict[q].extend(group) #extend the list of observations with a new list of observations in that category
      else: 
        repair_bin_dict[q] = group #otherwise key that category index and set it's value as the group list in that category
  print "Overflow of " + str(overflow)
  new_feature = Feature(repair_data,True) #initialize our new_feature (repaired feature)
  new_feature.bin_fulldata = repair_bin_dict
  return [new_feature,overflow]


def test():
  all_data = [ 
  ["x","A"],
  ["x","A"],
  ["x","B"],
  ["x","B"],
  ["x","B"],
  ["y","A"],
  ["y","A"],
  ["y","A"],
  ["y","B"],
  ["z","A"],
  ["z","A"],
  ["z","A"],
  ["z","A"],
  ["z","A"],
  ["z","B"]]
  #feature_to_repair is really feature to repair ON
  feature_to_repair = 0
  repair_level=1
  repair_amount = 1
  repairer = Repairer(all_data, feature_to_repair, repair_level)
  print repairer.repair(all_data, repair_amount)

if __name__== "__main__":
  test()
