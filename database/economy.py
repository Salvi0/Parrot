from pymongo import MongoClient
from utilities.config import my_secret

cluster = MongoClient(
    f"mongodb+srv://user:{str(my_secret)}@cluster0.xjask.mongodb.net/myFirstDatabase?retryWrites=true&w=majority"
)
db = cluster["economy"]
collection = db["global_economy"]


async def ge_update(user_id: int, bank: int, wallet: int):
    pre_post = {"_id": user_id}
    post = {'bank': bank, 'wallet': wallet}

    collection.update_one(pre_post, {"$set": post})



async def ge_on_join(user_id: int):
    post = {'_id': user_id, 'bank': 0, 'wallet': 400}


    collection.insert_one(post)
