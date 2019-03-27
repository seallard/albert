import csv
import pandas as pd
import numpy as np

from keras.models import load_model
from validation_dataset import team_average

from datetime import date
from datetime import timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import getpass

# Choose model 1 (uses home+away average) or 5 (uses away or home averages).
model_name = input("Choose net, 1 (tested, ca 70 % acc) or 5 (not tested yet):  \n")
model = load_model("../trained network/net_{}".format(model_name))

# Load data set to calculate season averages below.
df = pd.read_csv("../data sets/prediction_dataset.csv")

username = input("Username: ")
password = getpass.getpass()

# Open bet365 page.
chrome_driver_path = "./chromedriver_win32/chromedriver.exe"
driver = webdriver.Chrome(executable_path=chrome_driver_path)
driver.maximize_window()

url = "https://www.bet365.com/#/AC/B18/C20604387/D48/E1453/F10/"
driver.get(url)
driver.get(url) # Get past advert.
time.sleep(1)

def bet_login(username, password):
    login = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'hm-Login')))
    fields = login.find_elements_by_css_selector('.hm-Login_InputField')
    button = login.find_element_by_css_selector('.hm-Login_LoginBtn')
    
    fields[0].send_keys(username)
    fields[1].click()
    fields[2].send_keys(password)
    button.click()

    # Switch frame and close message on log in.
    iframe = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'messageWindow')))
    driver.switch_to.frame(iframe)
    button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#Continue')))
    button.click()
    driver.switch_to.default_content()

bet_login(username, password)

def get_balance():
    "Returns account balance."
    driver.switch_to.default_content()
    balance = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'hm-Balance '))).text.split(" ")[0]
    return int(balance.split(",")[0])

def kelly_criterion(odds, prediction):
    balance = get_balance()
    bet = round(balance*0.3*(odds*prediction-(1-prediction))/odds)
    return bet

# Collect games and odds from bookmaker.
teams = driver.find_elements_by_class_name("sl-CouponParticipantGameLineTwoWay_NameText ")
team_iterator = iter([team.text.split(" ")[-1] for team in teams])
games = list(zip(team_iterator, team_iterator)) # Tuples (away team, home team).

odds = driver.find_elements_by_class_name("gl-ParticipantCentered_NoHandicap")
odds = [odd.text for odd in odds][-len(teams):]
odds_iterator = iter([float(odd) for odd in odds])
odds = list(zip(odds_iterator, odds_iterator)) # Tuples (away odds, home odds).

bets_x_path = "/html/body/div[1]/div/div[2]/div[1]/div/div[2]/div[2]/div/div[2]/div[2]/div/div[5]/div"

def place_bet(amount, bet_row_index):
    # Click on odds
    driver.find_element_by_xpath(bets_x_path + "[{}]".format(bet_row_index)).click()

    # Switch frame
    iframe = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'bsFrame')))
    driver.switch_to.frame(iframe)
        
    # Set amount
    set_amount = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#bsDiv > ul > li.single-section.bs-StandardBet > ul > li > div.stake.bs-StakeData > div.bs-StakeAndToReturnContainer > div.bs-Stake > input')))
    set_amount.send_keys(str(amount))
    
    # Confirm
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#bsDiv > ul > li.bs-Footer.placebet'))).click()

    # Switch back
    driver.switch_to.default_content()


print("------------------------------------------------------------------")

with open("../data sets/make_prediction.csv", "a", newline='') as outfile:
    filewriter = csv.writer(outfile,delimiter=',',quoting=csv.QUOTE_MINIMAL)
    bet_row_index = 2
    
    # Make prediction for each game.
    for i, game in enumerate(games):

        away_team, home_team = game
        print("Away: " + away_team)
        print("Home: " + home_team)


        # Fix name error.
        if away_team == "Blazers":
            away_team = "Trail Blazers"
        
        if home_team == "Blazers":
            home_team = "Trail Blazers"

        # Calculate season averages for teams.
        home_team_averages = team_average(home_team, len(df), df, "home", model_name)
        away_team_averages = team_average(away_team, len(df), df, "away", model_name)
        
        # Input vector of home team and away team averages.
        game = np.asarray([home_team_averages + away_team_averages])
        
        # Make prediction.
        home_prediction = model.predict(game)[0][0]
        away_prediction = 1-home_prediction

        # Calculate bookmakers implied probabilities. 
        away_odds, home_odds = odds[i]
        bookmakers_fee = 1.041
        home_implied_probability = round(1/(home_odds*bookmakers_fee), 3)
        away_implied_probability = round(1/(away_odds*bookmakers_fee), 3)
        
        print("Implied probability: {:.3f}% that {} wins. Odds: {}".format(home_implied_probability*100, home_team, home_odds))
        print("Prediction: {:.3f}% that {} wins.".format(home_prediction*100, home_team))
        
        print("Implied probability: {:.3f}% that {} will win. Odds: {}".format(away_implied_probability*100, away_team, away_odds))
        print("Prediction: {:.3f}% that {} wins.".format(away_prediction*100, away_team))

        if (away_prediction > 0.5) and (away_prediction > away_implied_probability) and (away_odds >= 1.4):
            amount = kelly_criterion(away_odds, away_prediction) 
            print("Bet {} on {}  row {}".format(amount, away_team, bet_row_index))
            #place_bet(amount, bet_row_index)
            time.sleep(1)
            bet_row_index += 2
        
        elif (home_prediction > 0.5) and (home_prediction > home_implied_probability) and (home_odds >= 1.4):
            bet_row_index += 1
            amount = kelly_criterion(home_odds, home_prediction)
            print("Bet {} on {} row {}".format(amount, home_team, bet_row_index))
            #place_bet(amount, bet_row_index)
            time.sleep(1)
            bet_row_index += 1

        else:
            bet_row_index += 2
            
        print("------------------------------------------------------------------")

        # Write to file.
        filewriter.writerow([home_team, away_team, str(date.today() + timedelta(days=1)), home_odds, away_odds, round(home_prediction, 3)])
