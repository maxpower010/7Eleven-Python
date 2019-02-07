'''
    7-Eleven Python implementation. This program allows you to lock in a fuel price from your computer.
    Copyright (C) 2018  Freyta

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <https://www.gnu.org/licenses/>.

'''

from flask import Flask, render_template, request, redirect, url_for, session, flash

import os
import hashlib
import hmac
import base64
import time
import uuid
import requests
import json
import random
import datetime
import googlemaps

'''''''''''''''''''''''''''

YOU ONLY NEED TO CHANGE THE
    ONE VARIABLE BELOW.
TO GET AN API KEY FOLLOW THIS LINK
https://developers.google.com/maps/documentation/embed/get-api-key
'''''''''''''''''''''''''''
gmapsAPIkey = "REPLACE API KEY"
API_BASE_URL = "https://711-goodcall.api.tigerspike.com/api/v1"


def cheapestFuelAll():
    # Just a quick way to get fuel prices from a website that is already created.
    # Thank you to master131 for this.
    r = requests.get("https://projectzerothree.info/api.php?format=json")
    response = json.loads(r.text)

    # E10
    session['postcode0'] = response['regions'][0]['prices'][0]['postcode']
    session['price0'] = response['regions'][0]['prices'][0]['price']

    # Unleaded 91
    session['postcode1'] = response['regions'][0]['prices'][1]['postcode']
    session['price1'] = response['regions'][0]['prices'][1]['price']

    # Unleaded 95
    session['postcode2'] = response['regions'][0]['prices'][2]['postcode']
    session['price2'] = response['regions'][0]['prices'][2]['price']

    # Unleaded 98
    session['postcode3'] = response['regions'][0]['prices'][3]['postcode']
    session['price3'] = response['regions'][0]['prices'][3]['price']

    # Diesel
    session['postcode4'] = response['regions'][0]['prices'][4]['postcode']
    session['price4'] = response['regions'][0]['prices'][4]['price']

    # LPG
    session['postcode5'] = response['regions'][0]['prices'][5]['postcode']
    session['price5'] = response['regions'][0]['prices'][5]['price']


def cheapestFuel(fueltype):
    # Gets the cheapest fuel price for a certain type of fuel and the postcode
    # This is used for the automatic lock in
    r = requests.get("https://projectzerothree.info/api.php?format=json")
    response = json.loads(r.text)
    '''
    52 = Unleaded 91
    53 = Diesel
    54 = LPG
    55 = Unleaded 95
    56 = Unleaded 98
    57 = E10
    '''
    if (fueltype == "52"):
        fueltype = 1
    if (fueltype == "53"):
        fueltype = 4
    if (fueltype == "54"):
        fueltype = 5
    if (fueltype == "55"):
        fueltype = 2
    if (fueltype == "56"):
        fueltype = 3
    if (fueltype == "57"):
        fueltype = 0

    # Get the postcode and price
    postcode = response['regions'][0]['prices'][fueltype]['postcode']
    price = response['regions'][0]['prices'][fueltype]['price']
    return postcode, price


def lockedPrices():
    # This function is used for getting our locked in fuel prices to display on the main page

    # Remove all of our previous error messages
    session.pop('ErrorMessage', None)


    # The FuelLock URL
    relativeURL = "/FuelLock/List"
    url = API_BASE_URL + relativeURL
    # Generate the tssa string for inclusion in the headers
    tssa = generateTssa(url, "GET", None, session['accessToken'])

    headers = {'User-Agent': 'Apache-HttpClient/UNAVAILABLE (java 1.4)',
               'Authorization': '%s' % tssa,
               'X-OsVersion': 'Android 8.1.0',
               'X-OsName': 'Android',
               'X-DeviceID': session['deviceID'],
               'X-AppVersion': '1.7.0.2009',
               'X-DeviceSecret': session['deviceSecret'],
               'Content-Type': 'application/json; charset=utf-8'}

    response = requests.get(url, headers=headers)
    returnContent = json.loads(response.content.decode('utf-8'))

    # An error occurs if we have never locked in a price before
    try:
        session['fuelLockId'] = returnContent[0]['Id']
        session['fuelLockStatus'] = returnContent[0]['Status']
        session['fuelLockActive'] = [0, 0, 0]
        session['fuelLockType'] = returnContent[0]['FuelGradeModel']
        session['fuelLockCPL'] = returnContent[0]['CentsPerLitre']
        session['fuelLockLitres'] = returnContent[0]['TotalLitres']

        try:
            ts = returnContent[0]['RedeemedAt']
            session['fuelLockRedeemed'] = datetime.datetime.fromtimestamp(ts).strftime('%d-%m-%Y at %H:%M:%S')
        except:
            session['fuelLockRedeemed'] = ""

        try:
            ts = returnContent[0]['ExpiresAt']
            session['fuelLockExpiry'] = datetime.datetime.fromtimestamp(ts).strftime('%d-%m-%Y at %H:%M:%S')
        except:
            pass

        if (session['fuelLockStatus'] == 0):
            session['fuelLockActive'][0] = "Active"

        elif (session['fuelLockStatus'] == 1):
            session['fuelLockActive'][1] = "Expired"

        elif (session['fuelLockStatus'] == 2):
            session['fuelLockActive'][2] = "Redeemed"

        return session['fuelLockId'], session['fuelLockStatus'], session['fuelLockType'], session['fuelLockCPL'], \
               session['fuelLockLitres'], session['fuelLockExpiry'], session['fuelLockRedeemed']

    except:
        # Since we haven't locked in a fuel price before
        session['fuelLockId'] = ""
        session['fuelLockStatus'] = ""
        session['fuelLockActive'] = ""
        session['fuelLockType'] = ""
        session['fuelLockCPL'] = ""
        session['fuelLockLitres'] = ""
        session['fuelLockRedeemed'] = ""
        session['fuelLockExpiry'] = ""

        return session['fuelLockId'], session['fuelLockStatus'], session['fuelLockType'], session['fuelLockCPL'], \
               session['fuelLockLitres'], session['fuelLockExpiry'], session['fuelLockRedeemed']


def getKey(encryptedKey):
    # get the hex from the encrypted secret key and then split every 2nd character into an array row
    # hex_string = hashlib.sha1("om.sevenel").encode(utf-8).hexdigest()
    hex_string = hashlib.sha1(("om.sevenel").encode('utf-8')).hexdigest()
    hex_array = [hex_string[i:i + 2] for i in range(0, len(hex_string), 2)]

    # Key is the returned key
    key = ""
    i = 0

    # Get the unobfuscated key
    while (i < len(encryptedKey)):
        length = i % (len(hex_array))
        key += chr(int(hex_array[length], 16) ^ int(encryptedKey[i]))

        i = i + 1
    return key


def generateTssa(url, method, payload=None, accessToken=None):
    """ Encrypts the optional payload data and generates a "tssa" string """

    # Initialse the tssa string elements http url, timestamp and UUID
    replace = url.replace("https", "http").lower()
    timestamp = int(time.time())
    uuidVar = str(uuid.uuid4())

    # Put all of the above data into one string
    str3 = key + method + replace + str(timestamp) + uuidVar

    if method == 'POST':
        # MD5 Hash the payload and then Base64 encode the hash if we are posting a payload
        encrypteddata = base64.b64encode(hashlib.md5(payload.encode()).digest())
        # Append the encrypted data
        str3 = str3 + encrypteddata.decode()

    # Encrypt the built string and base64 encode
    signature = base64.b64encode(hmac.new(key2, str3.encode(), digestmod=hashlib.sha256).digest())
    # Build the tssa string
    tssaString = "tssa " + key + ":" + signature.decode() + ":" + uuidVar + ":" + str(timestamp)

    # Check if an accessToken has been generated for the session and append to the tssaString
    if session['accessToken']:
        tssaString = tssaString + ":" + session['accessToken']

    return tssaString


# key is the OBFUSCATED_APP_ID
key = getKey(
    [36, 132, 5, 129, 42, 105, 114, 152, 34, 137, 126, 125, 93, 11, 117, 200, 157, 243, 228, 226, 40, 210, 84, 134, 43,
     56, 37, 144, 116, 137, 43, 45])
# key2 is the OBFUSCATED_API_ID
key2 = base64.b64decode(getKey(
    [81, 217, 3, 192, 45, 88, 67, 253, 91, 164, 110, 13, 28, 57, 22, 225, 246, 233, 153, 224, 87, 152, 65, 253, 2, 115,
     83, 197, 64, 156, 94, 41, 25, 27, 116, 153, 150, 161, 188, 166, 113, 130, 83, 143]))
# The current time
timeNow = int(time.time())

app = Flask(__name__)


@app.route('/')
def index():
    # If they have pressed the refresh link remove the error and success messages
    if (request.args.get('action') == "refresh"):
        session.pop('ErrorMessage', None)
        session.pop('SuccessMessage', None)

    # Get the cheapest fuel price to show on the automatic lockin page
    fuelPrice = cheapestFuelAll()
    return render_template('price.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    # Clear the error and success message
    session.pop('ErrorMessage', None)
    session.pop('SuccessMessage', None)

    # Use a default deviceID for the session on login
    session['deviceID'] = "619a7dcdb433b27"
    session['accessToken'] = ""

    if request.method == 'POST':
        password = str(request.form['password'])
        email = str(request.form['email'])

        # The JSON payload to login
        payload = '{"Email":"' + email + '","Password":"' + password + '","DeviceName":"HUAWEIP9","DeviceOsNameVersion":"Android 8.1.0"}'

        # The login URL
        relativeURL = "/account/login"
        url = API_BASE_URL + relativeURL
        # Generate the tssa string for inclusion in the headers
        tssa = generateTssa(url, "POST", payload)

        headers = {'User-Agent': 'Apache-HttpClient/UNAVAILABLE (java 1.4)',
                   'Authorization': '%s' % tssa,
                   'X-OsVersion': 'Android 8.1.0',
                   'X-OsName': 'Android',
                   'X-DeviceID': session['deviceID'],
                   'X-AppVersion': '1.7.0.2009',
                   'Content-Type': 'application/json; charset=utf-8'}

        response = requests.post(url, data=payload, headers=headers)

        returnHeaders = response.headers
        returnContent = json.loads(response.text)

        try:
            # If there was an error logging in, redirect to the index page with the 7Eleven response
            if (returnContent['Message']):
                session['ErrorMessage'] = returnContent['Message']
                return redirect(url_for('index'))

        except:

            # We need the AccessToken from the response header
            accessToken = str(returnHeaders).split("'X-AccessToken': '")
            accessToken = accessToken[1].split("'")
            accessToken = accessToken[0]

            # DeviceSecretToken and accountID are both needed to lock in a fuel price
            deviceSecret = returnContent['DeviceSecretToken']
            accountID = returnContent['AccountId']
            # Save the users first name and their card balance so we can display it
            firstName = returnContent['FirstName']
            cardBalance = str(returnContent['DigitalCard']['Balance'])

            session['deviceSecret'] = deviceSecret
            session['accessToken'] = accessToken
            session['accountID'] = accountID
            session['firstName'] = firstName
            session['cardBalance'] = cardBalance

            lockedPrices()
            return redirect(url_for('index'))
    else:
        # They didn't submit a POST request, so we will redirect to index
        return redirect(url_for('index'))


@app.route('/logout')
def logout():
    # The logout payload is an empty string but it is still needed
    payload = '""'

    # The logout URL and a current timestamp + UUID

    relativeURL = "/account/logout"
    url = API_BASE_URL + relativeURL
    # Generate the tssa string for inclusion in the headers
    tssa = generateTssa(url, "POST", payload, session['accessToken'])

    headers = {'User-Agent': 'Apache-HttpClient/UNAVAILABLE (java 1.4)',
               'Authorization': '%s' % tssa,
               'X-OsVersion': 'Android 8.1.0',
               'X-OsName': 'Android',
               'X-DeviceID': session['deviceID'],
               'X-AppVersion': '1.7.0.2009',
               'X-DeviceSecret': session['deviceSecret'],
               'Content-Type': 'application/json; charset=utf-8'}

    response = requests.post(url, data=payload, headers=headers)
    # Clear all of the previously set session variables and then redirect to the index page
    session.clear()
    return redirect(url_for('index'))


@app.route('/lockin', methods=['POST', 'GET'])
def lockin():
    if request.method == 'POST':
        # Variable used to search for a manual price
        priceOveride = False

        # Get the fuel type we want
        fuelType = str(request.form['fueltype'])

        # Clear previous messages
        session.pop('ErrorMessage', None)
        session.pop('SuccessMessage', None)

        # Get the postcode and price of the cheapest fuel
        locationResult = cheapestFuel(fuelType)

        # Initiate the google maps API
        gmaps = googlemaps.Client(key=gmapsAPIkey)

        # Get the Latitude and Longitude from the postcode of the cheapest station
        if (request.form['submit'] == "automatic"):
            geocode_result = gmaps.geocode(str(locationResult[0]) + ', Australia')
            locLat = str(geocode_result[0]['geometry']['location']['lat'])
            locLong = str(geocode_result[0]['geometry']['location']['lng'])
            location = locLat + "," + locLong

        elif (request.form['submit'] == "manual"):
            # Since we have manually chosen a location, set priceOveride to true
            priceOveride = True
            geocode_result = gmaps.geocode(str(request.form['postcode']) + ', Australia')
            locLat = str(geocode_result[0]['geometry']['location']['lat'])
            locLong = str(geocode_result[0]['geometry']['location']['lng'])
            location = locLat + "," + locLong
        else:
            # They tried to do something different from the manual and automatic form, so throw up an error
            session[
                'ErrorMessage'] = "Invalid form submission. Either use the manual or automatic one on the main page."
            return redirect(url_for('index'))

        # If the fuel type is not within our boundaries (52 = E10, 58 = LPG) throw up an error
        if (fuelType < "52" or fuelType > "58"):
            session['ErrorMessage'] = "Invalid fuel type selected. Try again!"
            return redirect(url_for('index'))

        # The payload encrypted data
        timestamp = int(time.time())
        payload = '{"LastStoreUpdateTimestamp":' + str(
            timestamp) + ',"Latitude":"' + locLat + '","Longitude":"' + locLong + '"}'

        # The FuelLock URL
        relativeURL = "/FuelLock/StartSession"
        url = API_BASE_URL + relativeURL
        # Generate the tssa string for inclusion in the headers
        tssa = generateTssa(url, "POST", payload, session['accessToken'])

        headers = {'User-Agent': 'Apache-HttpClient/UNAVAILABLE (java 1.4)',
                   'Authorization': '%s' % tssa,
                   'X-OsVersion': 'Android 8.1.0',
                   'X-OsName': 'Android',
                   'X-DeviceID': session['deviceID'],
                   'X-AppVersion': '1.7.0.2009',
                   'X-DeviceSecret': session['deviceSecret'],
                   'Content-Type': 'application/json; charset=utf-8'}

        # Send the request
        response = requests.post(url, data=payload, headers=headers)

        # Get the response content so we can check the fuel price
        returnContent = response.content

        # Move the response json into an array so we can read it
        returnContent = json.loads(returnContent)
        # Get the store number - I don't think we need this, so I have commented it out!
        # storeNumber = returnContent['CheapestFuelTypeStores'][0]['StoreNumber']

        # If there is a fuel lock already in place we get an error!
        try:
            if returnContent['ErrorType'] == 0:
                session[
                    'ErrorMessage'] = "An error has occured. This is most likely due to a fuel lock already being in place."
                return redirect(url_for('index'))
        except:
            pass

        # Get the fuel price of all the types of fuel
        for each in returnContent['CheapestFuelTypeStores']:
            x = each['FuelPrices']
            for i in x:
                if (str(i['Ean']) == fuelType):
                    LockinPrice = i['Price']

        # If we have performed an automatic search we run the lowest price check
        # LockinPrice = the price from the 7/11 website
        # locationResult[1] = the price from the master131 script
        # If the price that we tried to lock in is more expensive than scripts price, we return an error
        if not (priceOveride):
            if not (float(LockinPrice) <= float(locationResult[1])):
                session[
                    'ErrorMessage'] = "The fuel price is too high compared to the cheapest available. The cheapest we found was at " + \
                                      locationResult[0] + ". Try locking in there!"
                return redirect(url_for('index'))

        # Now we want to lock in the maximum litres we can.
        NumberOfLitres = int(float(session['cardBalance']) / LockinPrice * 100)

        # Lets start the actual lock in process
        payload = '{"AccountId":"' + session['accountID'] + '","FuelType":"' + fuelType + '","NumberOfLitres":"' + str(
            NumberOfLitres) + '"}'

        # The FuelLock URL for locking in the price
        relativeURL = "/FuelLock/Confirm"
        url = API_BASE_URL + relativeURL
        # Generate the tssa string for inclusion in the headers
        tssa = generateTssa(url, "POST", payload, session['accessToken'])

        headers = {'User-Agent': 'Apache-HttpClient/UNAVAILABLE (java 1.4)',
                   'Authorization': '%s' % tssa,
                   'X-OsVersion': 'Android 8.1.0',
                   'X-OsName': 'Android',
                   'X-DeviceID': session['deviceID'],
                   'X-AppVersion': '1.7.0.2009',
                   'X-DeviceSecret': session['deviceSecret'],
                   'Content-Type': 'application/json; charset=utf-8'}

        # Send through the request and get the response
        response = requests.post(url, data=payload, headers=headers)

        # Get the respons einto a json array
        returnContent = json.loads(response.content)
        try:
            # Check if the response was an error message
            if (returnContent['Message']):
                # If it is, get the error message and return back to the index
                session['ErrorMessage'] = returnContent['Message']
                return redirect(url_for('index'))
            # Otherwise we most likely locked in the price!
            if (returnContent['Status'] == "0"):
                # Update the fuel prices that are locked in
                lockedPrices()
                # Get amoount of litres that was locked in from the returned JSON array
                session['TotalLitres'] = returnContent['TotalLitres']
                session['SuccessMessage'] = "The price was locked in for " + str(LockinPrice) + " cents per litre"
                return redirect(url_for('index'))

        # For whatever reason it saved our lockin anyway and return to the index page
        except:
            # Update the fuel prices that are locked in
            lockedPrices()
            session['SuccessMessage'] = "The price was locked in for " + str(LockinPrice) + " cents per litre"
            # Get amoount of litres that was locked in from the returned JSON array
            session['TotalLitres'] = returnContent['TotalLitres']
            return redirect(url_for('index'))
    else:
        # They just tried to load the lockin page without sending any data
        session['ErrorMessage'] = "Unknown error occured. Please try again!"
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.secret_key = os.urandom(12)
    app.run(debug=True, host='0.0.0.0')
