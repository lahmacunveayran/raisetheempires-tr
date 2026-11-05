import sys, os
sys.path.insert(0, os.getcwd())
import megaseries, quest_trees
print("MS", megaseries.PLAYABLE, list(megaseries.SERIES))
print("QT", quest_trees.PLAYABLE[:5], len(quest_trees.PLAYABLE), len(quest_trees.TREES))
t = quest_trees.TREES[quest_trees.PLAYABLE[0]]
print(t.get('-totalQuestTreeAllies'), t.get('-rewardQuest'), t.get('criteria'), t.get('-initializeFirstQuest'))
for tid in quest_trees.PLAYABLE[:3]:
    print(tid, quest_trees.TREES[tid].get('criteria'), quest_trees.TREES[tid].get('-rewardQuest'), quest_trees.TREES[tid].get('-totalQuestTreeAllies'))
