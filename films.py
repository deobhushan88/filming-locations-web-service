# 1. Get source and destination lat, long from web service URL
# 2. Make a call to Google Maps Directions API
# 3. Get the end_location from each step, and add them to a centerCoords list in format [longitude, latitude] as required by Mongo DB
# 4. Construct Mongo DB queries using the co-ordinates in the centerCoords list

from bottle import request, response, route, run
import requests
from pymongo import MongoClient
import json
import decimal

@route('/films')
def return_films():

	# Getting the origin/source and destination from the URL. They will be comma seperated: lat,long
	source1 = request.query.origin
        destination1 = request.query.destination
        scomma = source1.find(",")
        dcomma = destination1.find(",")
        clat1 = float(source1[:scomma])
        clong1 = float(source1[scomma+1:])
        clat2 = float(destination1[:dcomma])
        clong2 = float(destination1[dcomma+1:])

	# Initialize list in which we will store the end_location from each step. NOT PUTTING START LOCATION AS IT WILL BE INCLUDED IN SOME
	# NEARBY STEP AREA ANYWAY. (ASSUMING MANY CLOSE STEPS WITHIN THE CITY LIMIT)
	ite = 0
	centerCoords = []

	# Getting the JSON response from Google Maps Directions API
	send_url = 'http://maps.googleapis.com/maps/api/directions/json?origin=' + str(clat1) + ',' + str(clong1) + '&destination=' + str(clat2) + ',' + str(clong2) + '&sensor=true'
	directions = requests.get(send_url)

	# Handling case where there was no route found between two points:
	if directions.json()["status"] == "ZERO_RESULTS":
		return json.loads('{"results":[], "total":0, "status":"NORESULTS"}')

	# Handling the peculiar structure of the JSON returned by Google Maps Directions 
	# See the sample JSON here: http://maps.googleapis.com/maps/api/directions/json?origin=Boulder,CO&destination=Phoenix,AZ&sensor=true
	routes = {}
	routes = directions.json()["routes"][0]
	legs = routes["legs"][0]
	steps = legs["steps"]

	# We now have a list in which each element is a dictionary detailing each step
	# Iterating through the list to get end_location of each step
	stepsLen = len(steps)
	count = 0
	for step in steps:
		count += 1
		end_location = step["end_location"]
		lng = end_location['lng']
		lat = end_location['lat']
		# Storing all values in the polygonCoords list. Skipping the last end_location, which is the destination coordinate
		# REASON: IT WILL BE INCLUDED IN SOME NEARBY STEP AREA ANYWAY. (ASSUMING MANY CLOSE STEPS WITHIN THE CITY LIMIT)
		if count < stepsLen:
			centerCoords.append([lng,lat])

	# MongoDB operations using pymongo
	client = MongoClient()
	db = client['272project']
	collection = db['results_location']

	# Creating and executing the Mongo DB query
	radius = 1/3959.0 # Miles expressed in radians.
	mongoQueryPREFIX = '{ "loc" :{ "$geoWithin" :{ "$centerSphere" : ['
	ite = 0
	total = 0
	returnString = ''
	idList = [] # Initialising a list which stores all _id fields from the result of each query. Will use this to eliminate duplicates
	queryLimit = 5 # Limiting number of results per query
	for each in centerCoords:
                ite += 1
		# Using Decimal to avoid rounding off when converting to string
		mongoQuery = mongoQueryPREFIX + '[' + str(decimal.Decimal(each[0])) + ',' + str(decimal.Decimal(each[1])) + ']' + ',' + str(decimal.Decimal(radius)) + '] }} }'
		queryDict = json.loads(mongoQuery)
		results = collection.find(queryDict).limit(queryLimit)
		resultsCount = results.count()
		count = 0
		for result in results:	# Will not execute if there were no results as the iterator will be empty
			count += 1
			tempJSONString = json.dumps(result)
			tempID = json.loads(tempJSONString)["_id"]
			if total == 0: # Adding total == 0 condition to avoid incrementing total again later in this for loop
				total += 1
				idList.append(tempID)
				returnString = '{"results":' + '[' + json.dumps(result) + ','
			# Eliminating duplicate films by using this if condition
			if tempID not in idList:
				idList.append(tempID)
				total += 1
				returnString = returnString + json.dumps(result) + ','
	# Handling the last element: Removing the comma at the end and adding the suffix fields
	returnString = returnString[:-1] + '], "total":' + str(total) + ', "status":"OK"}'
	print returnString				
	if total== 0:
                returnString = '{"results":[], "total":0, "status":"NORESULTS"}'

	returnDict = json.loads(returnString)

	return returnDict

# Running the web service
run(host='localhost', port=8080, debug=True)





	
