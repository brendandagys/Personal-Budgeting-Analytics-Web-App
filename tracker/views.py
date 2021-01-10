from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
# from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.core.mail import EmailMessage

from django.db.models import Q

# from django.contrib.auth.mixins import LoginRequiredMixin # Done in urls.py
from django.contrib.auth.decorators import login_required

from django.views import generic
from .forms import PurchaseForm, AccountForm, RecurringForm, QuickEntryForm, ProfileForm
from django.forms import modelformset_factory, NumberInput, TextInput, CheckboxInput, Select # Could have imported from .forms, if imported there
from .models import Purchase, QuickEntry, Filter, Recurring, Alert, PurchaseCategory, Account, AccountUpdate, Profile

from django.db.models import Sum

from math import floor
from decimal import Decimal
import datetime
import calendar
from dateutil.relativedelta import *
# import re # Was used in modelformset_factory, but then no longer needed
import pandas as pd

from forex_python.converter import CurrencyRates, CurrencyCodes
cr = CurrencyRates()
cc = CurrencyCodes()

def current_date():
    return datetime.date.today()

# Get information about today's date
# date = datetime.date.today()
# year = date.year
# month = date.month
# month_name = calendar.month_name[date.month]
# day = date.day
# weekday = date.weekday()


def get_purchase_categories_tuples_list(user_object):
    # To generate the filter buttons on Purchase Category and provide context for the green_filters class
    purchase_categories_list = []
    # Only include the ones that have actually been used thus far by the user
    category_values_used = list(Purchase.objects.filter(user=user_object).values_list('category__category', flat=True).distinct())
    category_2_values_used = list(Purchase.objects.filter(user=user_object).values_list('category_2__category', flat=True).distinct())
    category_2_values_used = [x for x in category_2_values_used if x] # Remove None
    purchase_categories_list = sorted(list(set(category_values_used + category_2_values_used)))

    purchase_categories_tuples_list = []
    for index in range(0, len(purchase_categories_list), 2):
        if index != len(purchase_categories_list) - 1:
            purchase_categories_tuples_list.append((purchase_categories_list[index], purchase_categories_list[index+1]))
        else:
            purchase_categories_tuples_list.append((purchase_categories_list[index], ))

    return purchase_categories_tuples_list


def get_exchange_rate(foreign_currency, desired_currency):
    return Decimal(cr.get_rate(foreign_currency, desired_currency))


def convert_currency(foreign_value, foreign_currency, desired_currency):
    # foreign_value = account_value # account_value is actually for another currency
    conversion_rate = get_exchange_rate(foreign_currency, desired_currency)
    return round(foreign_value * conversion_rate, 2) # Convert the currency ... multiplying produces many decimal places, so must round (won't matter for model field, though)


@login_required
def account_update(request):
    if request.method == 'POST':
        user_object = request.user

        dict = { request.POST['id']: '${:20,.2f}'.format(Decimal(request.POST['value'])) }

        if request.POST['id'][3:] == user_object.profile.credit_account.account: # If the Account updated was my credit card, check if the balance was paid off rather than added to
            credit_account_balance = AccountUpdate.objects.filter(account=user_object.profile.credit_account).order_by('-timestamp').first().value # Order should be preserved from models.py Meta options, but being safe
            if Decimal(request.POST['value']) < credit_account_balance: # If the balance was paid off, the chequing account should be decremented
                debit_account_balance = AccountUpdate.objects.filter(account=user_object.profile.debit_account).order_by('-timestamp').first().value
                AccountUpdate.objects.create(account=user_object.profile.debit_account, value=debit_account_balance-(credit_account_balance - Decimal(request.POST['value'])), exchange_rate=get_exchange_rate(user_object.profile.debit_account.currency, 'CAD'))
                dict.update({'id_' + user_object.profile.debit_account.account: '${:20,.2f}'.format(Decimal(debit_account_balance-(credit_account_balance - Decimal(request.POST['value']))))})

        AccountUpdate.objects.create(account=Account.objects.get(user=user_object, account=request.POST['id'][3:]), value=request.POST['value'], exchange_rate=get_exchange_rate(Account.objects.get(user=user_object, account=request.POST['id'][3:]).currency, 'CAD')) # id is prefixed with 'id_'

        return JsonResponse(dict)


@login_required
def reset_credit_card(request): # This function won't run unless both are defined, because the button is disabled if so
    user_object = request.user

    debit_account_balance = AccountUpdate.objects.filter(account=user_object.profile.debit_account).order_by('-timestamp').first().value # Order should be preserved from models.py Meta options, but being safe
    credit_account_balance = AccountUpdate.objects.filter(account=user_object.profile.credit_account).order_by('-timestamp').first().value # Order should be preserved from models.py Meta options, but being safe
    AccountUpdate.objects.create(account=user_object.profile.credit_account, value=0, exchange_rate=get_exchange_rate(user_object.profile.credit_account.currency, 'CAD'))
    AccountUpdate.objects.create(account=user_object.profile.debit_account, value=debit_account_balance-credit_account_balance, exchange_rate=get_exchange_rate(user_object.profile.debit_account.currency, 'CAD'))

    return JsonResponse({'debit_account': request.user.profile.debit_account.account,
                         'credit_account': request.user.profile.credit_account.account,
                         'debit_account_balance': '${:20,.2f}'.format(debit_account_balance-credit_account_balance)}, safe=False)


@login_required
def get_accounts_sum(request):
    user_object = request.user

    accounts_sum = 0

    for account in Account.objects.filter(user=user_object):
        account_value = 0 if AccountUpdate.objects.filter(account=account).order_by('-timestamp').first() is None else AccountUpdate.objects.filter(account=account).order_by('-timestamp').first().value
        account_value*=-1 if account.credit else 1 # If a 'credit' account, change sign before summing with the cumulative total

        if account.currency != 'CAD':
            foreign_value = account_value
            account_value = convert_currency(account_value, account.currency, 'CAD')

            # Different currency symbol formatting for American dollars
            USD_suffix = ''
            if account.currency == 'USD':
                USD_suffix = ' USD'

            print('Account \'{}\' converted from {}{}{} to ${} CAD.'.format(account.account, cc.get_symbol(account.currency), foreign_value, USD_suffix, account_value))

        accounts_sum+=account_value


    CAD_USD_rate = cc.get_symbol('USD') + str(round(get_exchange_rate('CAD', 'USD'), 3))
    CAD_EUR_rate = cc.get_symbol('EUR') + str(round(get_exchange_rate('CAD', 'EUR'), 3))

    USD_CAD_rate = '$' + str(round(get_exchange_rate('USD', 'CAD'), 3))
    EUR_CAD_rate = '$' + str(round(get_exchange_rate('EUR', 'CAD'), 3))

    return JsonResponse({ 'accounts_sum': '${:20,.2f}'.format(accounts_sum), 'exchange_rates': { 'CAD_USD': CAD_USD_rate, 'CAD_EUR': CAD_EUR_rate, 'USD_CAD': USD_CAD_rate, 'EUR_CAD': EUR_CAD_rate } }, safe=False)


@login_required
def get_json_queryset(request):
    user_object = request.user

    filter_instance = Filter.objects.get(user=user_object, page='Activity') # get_or_create() run in PurchaseListView get_context_data()

    start_date_filter = filter_instance.start_date_filter
    end_date_filter = filter_instance.end_date_filter

    if start_date_filter is None:
        start_date_filter = '2015-01-01'

    if end_date_filter is None:
        end_date_filter = '2099-12-31'

    if isinstance(start_date_filter, str):
        start_date_filter = datetime.datetime.strptime(start_date_filter, '%Y-%m-%d').date()

    if isinstance(end_date_filter, str):
        end_date_filter = datetime.datetime.strptime(end_date_filter, '%Y-%m-%d').date()

    days_difference = (end_date_filter - start_date_filter).days + 1


    purchase_categories_list = [x.id for x in [filter_instance.category_filter_1, filter_instance.category_filter_2, filter_instance.category_filter_3, filter_instance.category_filter_4, filter_instance.category_filter_5,
                                               filter_instance.category_filter_6, filter_instance.category_filter_7, filter_instance.category_filter_8, filter_instance.category_filter_9, filter_instance.category_filter_10,
                                               filter_instance.category_filter_11, filter_instance.category_filter_12, filter_instance.category_filter_13, filter_instance.category_filter_14, filter_instance.category_filter_15,
                                               filter_instance.category_filter_16, filter_instance.category_filter_17, filter_instance.category_filter_18, filter_instance.category_filter_19, filter_instance.category_filter_20,
                                               filter_instance.category_filter_21, filter_instance.category_filter_22, filter_instance.category_filter_23, filter_instance.category_filter_24, filter_instance.category_filter_25]
                                               if x is not None]


    periods = []
    sums = []

    for x in range(1, 5):
        temp_start_date = start_date_filter-datetime.timedelta(days=x*days_difference)
        temp_end_date = start_date_filter-datetime.timedelta(days=x*days_difference)+datetime.timedelta(days=days_difference-1)
        periods.append('{} - {}'.format(temp_start_date, temp_end_date))

        temp_queryset = Purchase.objects.filter(user=user_object, date__gte=temp_start_date, date__lte=temp_end_date)

        # Get the total cost of all of the purchases
        past_purchases_sum = 0
        for purchase in list(temp_queryset.values_list('category', 'category_2', 'amount', 'amount_2')): # Returns a Queryset of tuples
            if purchase[0] in purchase_categories_list: # If first category matches, always add 'amount'
                past_purchases_sum+=purchase[2]
            if purchase[1] in purchase_categories_list: # If second category matches...
                if purchase[3] is not None: # If there is a second value, always add it
                    past_purchases_sum+=purchase[3]
                elif purchase[0] not in purchase_categories_list: # If no 'amount_2', and first category DIDN'T match (we don't want to double-count), add 'amount' (in this case first three of tuple are populated)
                    past_purchases_sum+=purchase[2]
        sums.append(past_purchases_sum)

    periods.reverse()
    sums.reverse()

    # print(days_difference)
    # print(periods)
    # print(sums)

    queryset_data = Purchase.objects.filter(Q(user=user_object) & Q(date__gte=start_date_filter) & Q(date__lte=end_date_filter) & (Q(category__in=purchase_categories_list) | Q(category_2__in=purchase_categories_list))).order_by('-date', '-time', 'category__category', 'item')

    purchases_list = list(queryset_data.values('id', 'date', 'time', 'item', 'category__category', 'amount', 'category_2__category', 'amount_2', 'description', 'receipt')) # List of dictionaries

    for dict in purchases_list:
        # Convert the stored path (media/image.png) to the full URL, and add to the object dict
        # if dict['receipt'] is not None: # May not have a receipt file
        try:
            dict['url'] = request.build_absolute_uri(Purchase.objects.get(id=dict['id']).receipt.url)#.replace('static/', '') # For some reason, this was appearing before the 'media/' prefix, and S3 was giving a Key Error
        # else:
        except Exception:
            dict['url'] = ''

    # Get the total cost of all of the purchases
    purchases_sum = 0
    for purchase in list(queryset_data.values_list('category', 'category_2', 'amount', 'amount_2')): # Returns a Queryset of tuples
        if purchase[0] in purchase_categories_list: # If first category matches, always add 'amount'
            purchases_sum+=purchase[2]
        if purchase[1] in purchase_categories_list: # If second category matches...
            if purchase[3] is not None: # If there is a second value, always add it
                purchases_sum+=purchase[3]
            elif purchase[0] not in purchase_categories_list: # If no 'amount_2', and first category DIDN'T match (we don't want to double-count), add 'amount' (in this case first three of tuple are populated)
                purchases_sum+=purchase[2]

    return JsonResponse({'data': purchases_list, 'purchases_sum': '${:20,.2f}'.format(purchases_sum), 'past_periods': {'labels': periods, 'values': sums}, 'categories_count': len(purchase_categories_list)}, safe=False)


@login_required # Don't think this is necessary
def get_purchases_chart_data(request):

    if request.method == 'GET':
        user_object = request.user

        filter_instance = Filter.objects.get(user=user_object, page='Homepage')

        start_date_filter = filter_instance.start_date_filter
        end_date_filter = filter_instance.end_date_filter

        print('Start date filter: ' + str(start_date_filter))
        print('End date filter: ' + str(end_date_filter))

        if start_date_filter is None or start_date_filter < Purchase.objects.filter(user=user_object).order_by('date').first().date:
            start_date_filter = Purchase.objects.filter(user=user_object).order_by('date').first().date # Date of first purchase recorded

        if end_date_filter is None:
            end_date_filter = current_date()

        print(start_date_filter)
        print(end_date_filter)

        print('Days on chart: ' + str((end_date_filter-start_date_filter).days))

        # Extract the current filter values
        category_filter_1 = filter_instance.category_filter_1; category_filter_2 = filter_instance.category_filter_2
        category_filter_3 = filter_instance.category_filter_3; category_filter_4 = filter_instance.category_filter_4
        category_filter_5 = filter_instance.category_filter_5; category_filter_6 = filter_instance.category_filter_6
        category_filter_7 = filter_instance.category_filter_7; category_filter_8 = filter_instance.category_filter_8
        category_filter_9 = filter_instance.category_filter_9; category_filter_10 = filter_instance.category_filter_10
        category_filter_11 = filter_instance.category_filter_11; category_filter_12 = filter_instance.category_filter_12
        category_filter_13 = filter_instance.category_filter_13; category_filter_14 = filter_instance.category_filter_14
        category_filter_15 = filter_instance.category_filter_15; category_filter_16 = filter_instance.category_filter_16
        category_filter_17 = filter_instance.category_filter_17; category_filter_18 = filter_instance.category_filter_18
        category_filter_19 = filter_instance.category_filter_19; category_filter_20 = filter_instance.category_filter_20
        category_filter_21 = filter_instance.category_filter_21; category_filter_22 = filter_instance.category_filter_22
        category_filter_23 = filter_instance.category_filter_23; category_filter_24 = filter_instance.category_filter_24
        category_filter_25 = filter_instance.category_filter_25

        # Make a list of the currently applied filters
        current_filter_list = [x.category if x is not None else x for x in [category_filter_1, category_filter_2, category_filter_3, category_filter_4, category_filter_5, category_filter_6, category_filter_7, category_filter_8, category_filter_9, category_filter_10,
                       category_filter_11, category_filter_12, category_filter_13, category_filter_14, category_filter_15, category_filter_16, category_filter_17, category_filter_18, category_filter_19, category_filter_20,
                       category_filter_21, category_filter_22, category_filter_23, category_filter_24, category_filter_25]]
        current_filter_list_unique = sorted(list(set([x for x in current_filter_list if x])))
        current_filter_list_unique_ids = [PurchaseCategory.objects.get(user=user_object, category=x).id for x in current_filter_list_unique] # To filter the Queryset below, we need to give a list of IDs to the category fields, as it's a foreign key
        print('Filters for chart: ' + str(current_filter_list_unique))


        queryset = Purchase.objects.filter(Q(user=user_object) & Q(category__in=current_filter_list_unique_ids) | Q(category_2__in=current_filter_list_unique_ids), date__gte=start_date_filter, date__lte=end_date_filter).values('date', 'category', 'category_2', 'amount', 'amount_2')

        def get_period_sum(queryset, start_date, end_date):
            # If the first PurchaseCategory matches, always add amount_1 to the total
            sum_1 = 0 if queryset.filter(category__in=current_filter_list_unique_ids, date__gte=start_date, date__lte=end_date).aggregate(Sum('amount'))['amount__sum'] is None else queryset.filter(category__in=current_filter_list_unique_ids, date__gte=start_date, date__lte=end_date).aggregate(Sum('amount'))['amount__sum']
            # If the second PurchaseCategory matches AND amount_2 is given, always add amount_2 to the total
            sum_2 = 0 if queryset.filter(category_2__in=current_filter_list_unique_ids, amount_2__gt=0, date__gte=start_date, date__lte=end_date).aggregate(Sum('amount_2'))['amount_2__sum'] is None else queryset.filter(category_2__in=current_filter_list_unique_ids, amount_2__gt=0, date__gte=start_date, date__lte=end_date).aggregate(Sum('amount_2'))['amount_2__sum']
            # If the second PurchaseCategory matches AND amount_2 is not given AND first PurchaseCategory didn't match (avoid double-counting), add amount_1 to the total
            sum_3 = 0 if queryset.filter(category_2__in=current_filter_list_unique_ids, amount_2__isnull=True, date__gte=start_date, date__lte=end_date).exclude(category__in=current_filter_list_unique_ids).aggregate(Sum('amount'))['amount__sum'] is None else queryset.filter(category_2__in=current_filter_list_unique_ids, amount_2__isnull=True, date__gte=start_date, date__lte=end_date).exclude(category__in=current_filter_list_unique_ids).aggregate(Sum('amount'))['amount__sum']

            return sum_1 + sum_2 + sum_3


        # DAILY CHART
        labels_daily = []
        values_daily = []

        for datetime_index in pd.date_range(start_date_filter, end_date_filter, freq='D'): # freq='D' is default; returns a DateTime index
            labels_daily.append(str(datetime_index.date()) + '  (' + calendar.day_name[datetime_index.weekday()][:2] + ')')

        for date in labels_daily:
            date = date[:-6] # Remove the prefix we just added so we can filter with the date

            sum_1 = 0 if queryset.filter(category__in=current_filter_list_unique_ids, date=date).aggregate(Sum('amount'))['amount__sum'] is None else queryset.filter(category__in=current_filter_list_unique_ids, date=date).aggregate(Sum('amount'))['amount__sum']
            sum_2 = 0 if queryset.filter(category_2__in=current_filter_list_unique_ids, amount_2__gt=0, date=date).aggregate(Sum('amount_2'))['amount_2__sum'] is None else queryset.filter(category_2__in=current_filter_list_unique_ids, amount_2__gt=0, date=date).aggregate(Sum('amount_2'))['amount_2__sum']
            sum_3 = 0 if queryset.filter(category_2__in=current_filter_list_unique_ids, amount_2__isnull=True, date=date).exclude(category__in=current_filter_list_unique_ids).aggregate(Sum('amount'))['amount__sum'] is None else queryset.filter(category_2__in=current_filter_list_unique_ids, amount_2__isnull=True, date=date).exclude(category__in=current_filter_list_unique_ids).aggregate(Sum('amount'))['amount__sum']

            values_daily.append(sum_1 + sum_2 + sum_3)


        # WEEKLY CHART
        dates_list = pd.date_range(start=start_date_filter, end=end_date_filter, freq='7D').strftime('%Y-%m-%d').tolist() # This will be a DateTimeIndex. Last two methods format the dates into strings and turn into a list
        if dates_list[-1] != str(end_date_filter):
            dates_list.append(str(end_date_filter)) # Ensure we get all data up to the end_date_filter, even if the interval leaves a remainder

        labels_weekly = []
        values_weekly = []

        for date in dates_list: # If the last date is greater than end_date_filter, change it to end_date_filter, add the label, and end loop
            end_date = str(datetime.datetime.strptime(date, '%Y-%m-%d').date()+datetime.timedelta(days=6))
            if date == str(end_date_filter): # Prevent showing a range like '01-01 - 01-01'. Instead, just show one date
                labels_weekly.append(date)
                break
            if end_date >= str(end_date_filter): # Make sure that the very last date is no greater than end_date_filter
                labels_weekly.append(date + ' - ' + str(end_date_filter))
                break
            labels_weekly.append(date + ' - ' + end_date)

        for date_range in labels_weekly:
            if ' - ' in date_range:
                start_date, end_date = date_range.split(' - ')
            else:
                start_date, end_date = (date_range, date_range)

            values_weekly.append(get_period_sum(queryset, start_date, end_date))

        labels_weekly = [x[5:10] + ' - ' + x[-5:] if ' - ' in x else x[5:] for x in labels_weekly] # Removing the year component, as the label is too long


        # BI-WEEKLY CHART
        dates_list = pd.date_range(start=start_date_filter, end=end_date_filter, freq='14D').strftime('%Y-%m-%d').tolist() # This will be a DateTimeIndex. Last two methods format the dates into strings and turn into a list
        if dates_list[-1] != str(end_date_filter):
            dates_list.append(str(end_date_filter)) # Ensure we get all data up to the end_date_filter, even if the interval leaves a remainder

        labels_biweekly = []
        values_biweekly = []

        for date in dates_list: # If the last date is greater than end_date_filter, change it to end_date_filter, add the label, and end loop
            end_date = str(datetime.datetime.strptime(date, '%Y-%m-%d').date()+datetime.timedelta(days=13))
            if date == str(end_date_filter): # Prevent showing a range like '01-01 - 01-01'. Instead, just show one date
                labels_biweekly.append(date)
                break
            if end_date >= str(end_date_filter): # Make sure that the very last date is no greater than end_date_filter
                labels_biweekly.append(date + ' - ' + str(end_date_filter))
                break
            labels_biweekly.append(date + ' - ' + end_date)

        for date_range in labels_biweekly:
            if ' - ' in date_range:
                start_date, end_date = date_range.split(' - ')
            else:
                start_date, end_date = (date_range, date_range)

            values_biweekly.append(get_period_sum(queryset, start_date, end_date))

        labels_biweekly = [x[5:10] + ' - ' + x[-5:] if ' - ' in x else x[5:] for x in labels_biweekly] # Removing the year component, as the label is too long


        # MONTHLY CHART
        dates_list = [start_date_filter] # List of datetime objects
        start_date_monthly = start_date_filter
        while start_date_monthly < end_date_filter: # Using pd.date_range() with freq = 'M', '1M', 'MS' all did not work!
            start_date_monthly+=relativedelta(months=+1)
            if start_date_monthly < end_date_filter:
                dates_list.append(start_date_monthly)
            else:
                dates_list.append(end_date_filter)
                break

        labels_monthly = []
        values_monthly = []

        for date in dates_list: # If the last date is greater than end_date_filter, change it to end_date_filter, add the label, and end loop
            end_date = date+relativedelta(months=+1)+relativedelta(days=-1)
            if date == end_date_filter:
                labels_monthly.append(str(date))
                break
            if end_date >= end_date_filter:
                labels_monthly.append(str(date) + ' - ' + str(end_date_filter))
                break
            labels_monthly.append(str(date) + ' - ' + str(end_date))

        for date_range in labels_monthly:
            if ' - ' in date_range:
                start_date, end_date = date_range.split(' - ')
            else:
                start_date, end_date = (date_range, date_range)

            values_monthly.append(get_period_sum(queryset, start_date, end_date))

        labels_monthly = [x[5:10] + ' - ' + x[-5:] if ' - ' in x else x[5:] for x in labels_monthly] # Removing the year component, as the label is too long


        return JsonResponse({'labels_daily': labels_daily, 'values_daily': values_daily, 'labels_weekly': labels_weekly, 'values_weekly': values_weekly,
                             'labels_biweekly': labels_biweekly, 'values_biweekly': values_biweekly, 'labels_monthly': labels_monthly, 'values_monthly': values_monthly})


@login_required
def get_net_worth_chart_data(request):
    user_object = request.user

    labels = []
    values = []

    queryset = AccountUpdate.objects.filter(account__user=user_object) # Ordered by -timestamp
    distinct_accounts_list = set(queryset.values_list('account', flat=True)) # List of ints

    latest_value_dict = {} # When an Account has no update on a certain date, the queryset will return None; we will then take the most-recent account value
    for account in distinct_accounts_list:
        latest_value_dict[account] = 0

    for datetime_index in pd.date_range(queryset.last().timestamp.date(), queryset.first().timestamp.date(), freq='D'): # freq='D' is default; returns a DateTime index
        labels.append(str(datetime_index.date()) + '  (' + calendar.day_name[datetime_index.weekday()][:2] + ')')

    for date in labels:
        start_date = date[:-6] # Remove the prefix we just added so we can filter with the date
        end_date = str(datetime.datetime.strptime(date[:-6], '%Y-%m-%d').date()+datetime.timedelta(days=1))

        queryset_one_date = queryset.filter(timestamp__gte=start_date, timestamp__lt=end_date) # Has all AccountUpdates on one given date

        accounts_sum = 0

        for account in distinct_accounts_list:
            account_object = Account.objects.get(id=account)

            last_account_update_on_date = queryset_one_date.filter(account=account_object).order_by('-timestamp').first()
            if last_account_update_on_date is None:
                last_account_value_on_date = latest_value_dict[account]
            else:
                last_account_value_on_date = last_account_update_on_date.value
                last_account_value_on_date*=-1 if account_object.credit else 1 # If a 'credit' account, change sign before summing with the cumulative total

                if account_object.currency != 'CAD':
                    foreign_value = last_account_value_on_date
                    last_account_value_on_date = convert_currency(last_account_value_on_date, account_object.currency, 'CAD')

                latest_value_dict[account] = last_account_value_on_date

            accounts_sum+=last_account_value_on_date

        values.append(accounts_sum)


    return JsonResponse({'labels': labels, 'values': values})


@login_required
def get_pie_chart_data(request):
    user_object = request.user

    data_dict = {'pie_labels': (), 'pie_values': ()}

    filter_instance = Filter.objects.get(user=user_object, page='Activity')

    purchase_categories_list = [x.category for x in [filter_instance.category_filter_1, filter_instance.category_filter_2, filter_instance.category_filter_3, filter_instance.category_filter_4, filter_instance.category_filter_5,
                                                     filter_instance.category_filter_6, filter_instance.category_filter_7, filter_instance.category_filter_8, filter_instance.category_filter_9, filter_instance.category_filter_10,
                                                     filter_instance.category_filter_11, filter_instance.category_filter_12, filter_instance.category_filter_13, filter_instance.category_filter_14, filter_instance.category_filter_15,
                                                     filter_instance.category_filter_16, filter_instance.category_filter_17, filter_instance.category_filter_18, filter_instance.category_filter_19, filter_instance.category_filter_20,
                                                     filter_instance.category_filter_21, filter_instance.category_filter_22, filter_instance.category_filter_23, filter_instance.category_filter_24, filter_instance.category_filter_25]
                                                     if x is not None]

    if len(purchase_categories_list) > 0:

        pie_data = []

        start_date_filter = filter_instance.start_date_filter
        end_date_filter = filter_instance.end_date_filter

        if start_date_filter is None:
            start_date_filter = '2015-01-01'

        if end_date_filter is None:
            end_date_filter = '2099-12-31'


        queryset = Purchase.objects.filter(user=user_object, date__gte=start_date_filter, date__lte=end_date_filter)

        for category in purchase_categories_list:
            pie_data.append((category, queryset.filter(Q(category__category=category) | Q(category_2__category=category)).count()))

        pie_data.sort(key=lambda x: x[1], reverse=True) # Reverse-sort the list of tuples by the second values: the counts

        pie_data = list(zip(*pie_data[:7])) # Only keep seven, for readability | * is unpacking operator | is a list of two tuples

        data_dict.update({ 'pie_labels': pie_data[0], 'pie_values': pie_data[1] })

    return JsonResponse(data_dict)


@login_required
def delete_purchase(request):
    user_object = request.user

    Purchase.objects.get(id=request.POST['id']).delete()
    print('\nDeleted Purchase: ' + str(request.POST['id']) + '\n')
    return HttpResponse()


@login_required
def homepage(request):
    user_object = request.user

    if request.method == 'GET':
        context = {}

        context['account_to_use'] = user_object.profile.account_to_use # None, if not set
        context['account_to_use_currency'] = context['account_to_use'].currency if context['account_to_use'] else None
        context['second_account_to_use'] = user_object.profile.second_account_to_use
        context['second_account_to_use_currency'] = context['second_account_to_use'].currency if context['second_account_to_use'] else None
        context['third_account_to_use'] = user_object.profile.third_account_to_use
        context['third_account_to_use_currency'] = context['third_account_to_use'].currency if context['third_account_to_use'] else None

        context['primary_currency'] = user_object.profile.primary_currency

        # Create a filter object if this user hasn't loaded any pages yet
        filter_instance = Filter.objects.get_or_create(user=user_object, page='Homepage')[0] # Returns a tuple (object, True/False depending on whether or not just created)

        context['start_date'] = '' if filter_instance.start_date_filter is None else str(filter_instance.start_date_filter)
        context['end_date'] = '' if filter_instance.end_date_filter is None else str(filter_instance.end_date_filter)


    elif request.method == 'POST':

        purchase_form = PurchaseForm(request.POST, request.FILES)
        # print(purchase_form.errors)
        # print(request.FILES)
        purchase_instance = Purchase()

        if purchase_form.is_valid():
            purchase_instance.user = user_object
            purchase_instance.date = purchase_form.cleaned_data['date']
            purchase_instance.time = purchase_form.cleaned_data['time'] # Cleaning done in forms.py
            purchase_instance.item = purchase_form.cleaned_data['item'].strip()
            purchase_instance.category = purchase_form.cleaned_data['category'] # Pretty sure that passing an integer (which is coming from the front-end) representing the id means you don't have to retrieve an actual object
            purchase_instance.amount = purchase_form.cleaned_data['amount']
            purchase_instance.category_2 = purchase_form.cleaned_data['category_2']
            purchase_instance.amount_2 = purchase_form.cleaned_data['amount_2']
            purchase_instance.description = purchase_form.cleaned_data['description'].strip() if len(purchase_form.cleaned_data['description'].strip()) == 0 or purchase_form.cleaned_data['description'].strip()[-1] == '.' else purchase_form.cleaned_data['description'].strip() + '.' # Add a period if not present
            purchase_instance.currency = purchase_form.cleaned_data['currency']
            purchase_instance.exchange_rate = get_exchange_rate(purchase_form.cleaned_data['currency'], 'CAD')
            purchase_instance.receipt = request.FILES['receipt'] if len(request.FILES) > 0 and request.FILES['receipt'].size < 50000001 else None # Make sure file was uploaded, and check size (also done in front-end)

            # If an account to charge was available, and chosen in front-end, create the appropriate AccountUpdate object...
            account_object_to_charge = Account.objects.get(user=user_object, account=purchase_form.cleaned_data['account_to_use']) if purchase_form.cleaned_data['account_to_use'] != '' else None
            purchase_instance.account = account_object_to_charge

            purchase_instance.save()


            if account_object_to_charge:
                account_balance = AccountUpdate.objects.filter(account=account_object_to_charge).order_by('-timestamp').first().value

                # Deal with the 2nd amount, which may be None
                amount_2 = 0
                if purchase_instance.amount_2 is not None:
                    amount_2 = purchase_instance.amount_2

                amount_to_charge = purchase_instance.amount + amount_2

                if account_object_to_charge.credit: # True if a credit account
                    amount_to_charge*=-1

                AccountUpdate.objects.create(account=account_object_to_charge, purchase=purchase_instance, value=account_balance-amount_to_charge, exchange_rate=purchase_instance.exchange_rate)


            return redirect('homepage')
#
#         # ALERTS
#         mode_instance = Mode.objects.last()
#
#         if mode_instance is None:
#             mode_instance = Mode.objects.create( mode='All' )
#
#         if mode_instance.mode == 'All':
#             total_spent_to_date_coffee = Purchase.objects.filter((Q(category='Coffee') | Q(category_2='Coffee')) & Q(date__gte=datetime.datetime(year, month, 1))).aggregate(Sum('amount'))
#             total_spent_to_date_groceries = Purchase.objects.filter((Q(category='Groceries') | Q(category_2='Groceries')) & Q(date__gte=datetime.datetime(year, month, 1))).aggregate(Sum('amount'))
#             total_spent_to_date_food_drinks = Purchase.objects.filter((Q(category='Food/Drinks') | Q(category_2='Food/Drinks')) & Q(date__gte=datetime.datetime(year, month, 1))).aggregate(Sum('amount'))
#             total_spent_to_date_restaurants = Purchase.objects.filter((Q(category='Restaurants') | Q(category_2='Restaurants')) & Q(date__gte=datetime.datetime(year, month, 1))).aggregate(Sum('amount'))
#             total_spent_to_date_gas = Purchase.objects.filter((Q(category='Gas') | Q(category_2='Gas')) & Q(date__gte=datetime.datetime(year, month, 1))).aggregate(Sum('amount'))
#             total_spent_to_date_dates = Purchase.objects.filter((Q(category='Dates') | Q(category_2='Dates')) & Q(date__gte=datetime.datetime(year, month, 1))).aggregate(Sum('amount'))
#             total_spent_to_date_household_supplies = Purchase.objects.filter((Q(category='Household Supplies') | Q(category_2='Household Supplies')) & Q(date__gte=datetime.datetime(year, month, 1))).aggregate(Sum('amount'))
#
#             a = total_spent_to_date_coffee['amount__sum']
#             b = total_spent_to_date_groceries['amount__sum']
#             c = total_spent_to_date_food_drinks['amount__sum']
#             d = total_spent_to_date_restaurants['amount__sum']
#             e = total_spent_to_date_gas['amount__sum']
#             f = total_spent_to_date_dates['amount__sum']
#             g = total_spent_to_date_household_supplies['amount__sum']
#             # If no money has been spent in a category, it will be None. This converts it to 0 if so
#             def check_none(variable):
#                 if variable is None:
#                     return 0
#                 else:
#                     return variable
#
#             a = check_none(a); b = check_none(b); c = check_none(c); d = check_none(d); e = check_none(e); f = check_none(f); g = check_none(g)
#
#             coffee_maximum = 20
#             groceries_maximum = 150
#             food_drinks_maximum = 50
#             restaurants_maximum = 100
#             gas_maximum = 75
#             dates_maximum = 100
#             household_supplies_maximum = 30
#
#             email_body = """\
# <html>
# <head></head>
# <body style="border-radius: 20px; padding: 1rem; color: black; font-size: 0.80rem; background-color: #d5e9fb">
# <u><h3>Monthly Spending in {}:</h3></u>
# <p style="margin-bottom: 0px; font-family: monospace; color: black"><b>Coffee</b>:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="display: inline-block; width: 70px;">${}/${}</span> - <b>({}%)</b></p> </br>
# <p style="margin-bottom: 0px; margin-top: 0px; font-family: monospace; color: black"><b>Groceries</b>:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="display: inline-block; width: 70px;">${}/${}</span> - <b>({}%)</b></p> </br>
# <p style="margin-bottom: 0px; margin-top: 0px; font-family: monospace; color: black"><b>Food/Drinks</b>:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="display: inline-block; width: 70px;">${}/${}</span> - <b>({}%)</b></p> </br>
# <p style="margin-bottom: 0px; margin-top: 0px; font-family: monospace; color: black"><b>Restaurants</b>:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="display: inline-block; width: 70px;">${}/${}</span> - <b>({}%)</b></p> </br>
# <p style="margin-bottom: 0px; margin-top: 0px; font-family: monospace; color: black"><b>Gas</b>:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="display: inline-block; width: 70px;">${}/${}</span> - <b>({}%)</b></p> </br>
# <p style="margin-bottom: 0px; margin-top: 0px; font-family: monospace; color: black"><b>Dates</b>:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="display: inline-block; width: 70px;">${}/${}</span> - <b>({}%)</b></p> </br>
# <p style="margin-top: 0px; font-family: monospace; color: black"><b>Household Supplies</b>: <span style="display: inline-block; width: 70px;">${}/${}</span> - <b>({}%)</b></p> </br>
# </body>
# </html>
# """.format(month_name,
#            a, coffee_maximum, round((a/coffee_maximum)*100, 1),
#            b, groceries_maximum, round((b/groceries_maximum)*100, 1),
#            c, food_drinks_maximum, round((c/food_drinks_maximum)*100, 1),
#            d, restaurants_maximum, round((d/restaurants_maximum)*100, 1),
#            e, gas_maximum, round((e/gas_maximum)*100, 1),
#            f, dates_maximum, round((f/dates_maximum)*100, 1),
#            g, household_supplies_maximum, round((g/household_supplies_maximum)*100, 1) )
#
#             email_message = EmailMessage('Spending Alert', email_body, from_email='Spending Helper <spendinghelper@gmail.com>', to=['brendandagys@gmail.com'])
#             email_message.content_subtype = 'html'
#             email_message.send()
#
#         elif mode_instance.mode == 'Threshold':
#
#             def check_spending(category, maximum):
#                 # Get all purchases of the specific type for the current month
#                 alert_queryset = Alert.objects.filter(type=category, date_sent__gte=datetime.datetime(year, month, 1))
#                 # If no alerts have been created, make one
#                 if len(alert_queryset) == 0:
#                     instance = Alert.objects.create( type=category,
#                                                      percent=0,
#                                                      date_sent=datetime.datetime(year, month, 1) )
#                 # Otherwise take the first alert received (there will only be one...four in total)
#                 else:
#                     instance = alert_queryset[0]
#                     # Check if a new month has begun, and reset if so
#                     if month != instance.date_sent.month:
#                         instance.date_sent.month = month
#                         instance.percent = 0
#
#                 highest_threshold_reached = instance.percent
#
#                 # Get total spent this month on the specific type
#                 total_spent_to_date = Purchase.objects.filter((Q(category=category) | Q(category_2=category)) & Q(date__gte=datetime.datetime(year, month, 1))).aggregate(Sum('amount'))
#                 total_spent_to_date = total_spent_to_date['amount__sum']
#
#                 send_email = True
#
#                 if total_spent_to_date is None:
#                     total_spent_to_date = 0
#
#                 if total_spent_to_date >= maximum:
#                     instance.percent = 100
#                     if highest_threshold_reached == 100:
#                         send_email = False
#
#                 elif total_spent_to_date >= floor(maximum * 0.75):
#                     instance.percent = 75
#                     if highest_threshold_reached >= 75:
#                         send_email = False
#
#                 elif total_spent_to_date >= floor(maximum * 0.5):
#                     instance.percent = 50
#                     if highest_threshold_reached >= 50:
#                         send_email = False
#
#                 elif total_spent_to_date >= floor(maximum * 0.25): # and (instance.percent < 25 or instance.percent in (50, 75, 100)):
#                     instance.percent = 25
#                     if highest_threshold_reached >= 25:
#                         send_email = False
#
#                 else:
#                     instance.percent = 0
#                     instance.save()
#                     return
#
#                 instance.save()
#
#                 if send_email is True:
#                     email_body = """\
# <html>
#   <head></head>
#   <body style="border-radius: 20px; padding: 1rem; color: black; font-size: 1.1rem; background-color: #d5e9fb">
#     <h3>You have reached {0}% of your monthly spending on {1}.</h3> </br>
#     <p>Spent in {2}: ${3}/${4}</p> </br>
#   </body>
# </html>
# """.format(round((total_spent_to_date/maximum)*100, 1), category, month_name, round(total_spent_to_date, 2), maximum)
#
#                     email_message = EmailMessage('Spending Alert for {0}'.format(category), email_body, from_email='Spending Helper <spendinghelper@gmail.com>', to=['brendandagys@gmail.com'])
#                     email_message.content_subtype = 'html'
#                     email_message.send()
#
#             # Run the function
#             check_spending('Coffee', 20)
#             check_spending('Groceries', 150)
#             check_spending('Food/Drinks', 50)
#             check_spending('Dates', 100)
#             check_spending('Restaurants', 100)
#             check_spending('Gas', 65)
#             check_spending('Household Supplies', 20)


    # This returns a blank form, (to clear for the next submission if request.method == 'POST')
    purchase_form = PurchaseForm()

    context['purchase_form'] = purchase_form
    context['purchase_categories_tuples_list'] = get_purchase_categories_tuples_list(user_object)

    return render(request, 'tracker/homepage.html', context=context)


class PurchaseListView(generic.ListView):
    # queryset = Purchase.objects.order_by('-date')
    # context_object_name = 'purchase_list'
    template_name = 'tracker/activity.html' # Specify your own template


    def get_queryset(self):
        pass


    def get_context_data(self, *args, **kwargs):
        user_object = self.request.user

        # Call the base implementation first to get a context
        context = super().get_context_data(*args, **kwargs) # Simply using context = {} works, but being safe...

        # To generate fields for me to update account balances
        context['account_form'] = AccountForm(user_object)

        context['debit_account'] = 'Not set'
        if user_object.profile.debit_account:
            context['debit_account'] = user_object.profile.debit_account.account

        context['credit_account'] = 'Not set'
        if user_object.profile.credit_account:
            context['credit_account'] = user_object.profile.credit_account.account

        # To fill the datepickers with the current date filters and label the active filters. Create a filter object if this user hasn't loaded any pages yet
        filter_instance = Filter.objects.get_or_create(user=user_object, page='Activity')[0] # Returns a tuple (object, True/False depending on whether or not just created)

        context['start_date'] = '' if filter_instance.start_date_filter is None else str(filter_instance.start_date_filter)
        context['end_date'] = '' if filter_instance.end_date_filter is None else str(filter_instance.end_date_filter)
        context['purchase_category_filters'] = [x.category for x in [filter_instance.category_filter_1, filter_instance.category_filter_2, filter_instance.category_filter_3, filter_instance.category_filter_4, filter_instance.category_filter_5,
                                                                     filter_instance.category_filter_6, filter_instance.category_filter_7, filter_instance.category_filter_8, filter_instance.category_filter_9, filter_instance.category_filter_10,
                                                                     filter_instance.category_filter_11, filter_instance.category_filter_12, filter_instance.category_filter_13, filter_instance.category_filter_14, filter_instance.category_filter_15,
                                                                     filter_instance.category_filter_16, filter_instance.category_filter_17, filter_instance.category_filter_18, filter_instance.category_filter_19, filter_instance.category_filter_20,
                                                                     filter_instance.category_filter_21, filter_instance.category_filter_22, filter_instance.category_filter_23, filter_instance.category_filter_24, filter_instance.category_filter_25]
                                                                     if x is not None]

        context['purchase_categories_tuples_list'] = get_purchase_categories_tuples_list(user_object)

        return context


@login_required
def settings(request):
    user_object = request.user

    if request.method == 'GET':
        if 'type' in request.GET:
            if request.GET['model'] == 'Profile':
                choices = ''
                for x in Account.objects.values('id', 'account'): # Using a generator or list comprehension wasn't working
                    choices+='<option value="{0}">{1}</option>'.format(x['id'], x['account'])

                return JsonResponse({'choices': choices,
                                     'values': {'account_to_use': user_object.profile.account_to_use.id,
                                                'second_account_to_use': user_object.profile.second_account_to_use.id,
                                                'third_account_to_use': user_object.profile.third_account_to_use.id,
                                                'credit_account': user_object.profile.credit_account.id,
                                                'debit_account': user_object.profile.debit_account.id,
                                                'primary_currency': user_object.profile.primary_currency,
                                    } })

            elif request.GET['model'] == 'Recurring':
                table_string = '''
<table id="recurring_table" style="table-layout:fixed; margin:auto; max-width:500px;" class="table table-sm table-striped table-bordered">
    <tr style="font-size:0.4rem; text-align:center;">
        <th>Name</th>
        <th style="width:11%">Type</th>
        <th>Account</th>
        <th>Category</th>
        <th style="width:11%">Active</th>
        <th style="width:13.5%">Amount</th>
        <th>Freq.</th>
    </tr>
'''

                for object in Recurring.objects.filter(user=user_object).values('name', 'type', 'account__account', 'category__category', 'active', 'amount'):
                    table_string+='''
    <tr class="hover" style="font-size:0.3rem; text-align:center;">
        <td style="vertical-align:middle;">{0}</td>
        <td style="vertical-align:middle;">{1}</td>
        <td style="vertical-align:middle;">{2}</td>
        <td style="vertical-align:middle;">{3}</td>
        <td style="vertical-align:middle;">{4}</td>
        <td style="vertical-align:middle;">{5}</td>
        <td style="vertical-align:middle;">{6}</td>
    </tr>
'''.format(object['name'], object['type'], str(object['account__account']).replace('None', ''), str(object['category__category']).replace('None', ''), object['active'], object['amount'], '')
                return JsonResponse(table_string + '</table>', safe=False)

            elif request.GET['model'] == 'Quick Entry':
                table_string = '''
<table style="table-layout:fixed; margin:auto; max-width:500px;" class="table table-sm table-striped table-bordered">
    <tr style="font-size:0.4rem; text-align:center;">
        <th style="width:7%">ID</th>
        <th>Category</th>
        <th>Item</th>
        <th style="width:13.5%">Amount</th>
        <th>Category 2</th>
        <th style="width:13.5%">Amount 2</th>
        <th>Specifics</th>
    </tr>
'''

                for object in QuickEntry.objects.filter(user=user_object).values('id', 'category__category', 'item', 'amount', 'category_2__category', 'amount_2', 'description'):
                    table_string+='''
    <tr style="font-size:0.3rem; text-align:center;">
        <td style="vertical-align:middle;">{0}</td>
        <td style="vertical-align:middle;">{1}</td>
        <td style="vertical-align:middle;">{2}</td>
        <td style="vertical-align:middle;">{3}</td>
        <td style="vertical-align:middle;">{4}</td>
        <td style="vertical-align:middle;">{5}</td>
        <td style="vertical-align:middle;">{6}</td>
    </tr>
'''.format(str(object['id']), str(object['category__category']).replace('None', ''), object['item'], object['amount'], str(object['category_2__category']).replace('None', ''), str(object['amount_2']).replace('None', ''), object['description'])
                return JsonResponse(table_string + '</table>', safe=False)


        else: # Inital page load
            context = {}

            ThresholdFormSet = modelformset_factory(PurchaseCategory,
                                                    fields=('id', 'category', 'threshold', 'threshold_rolling_days'),
                                                    widgets={'category': TextInput(attrs={'class': 'form-control form-control-sm', 'style': 'width:180px;'}),
                                                             'threshold': NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width:95px;', 'inputmode': 'decimal'}),
                                                             'threshold_rolling_days': NumberInput(attrs={'class': 'form-control form-control-sm', 'style': 'width:53px;', 'inputmode': 'numeric'})})

            AccountFormSet = modelformset_factory(Account,
                                                  exclude=(),
                                                  widgets={'account': TextInput(attrs={'class': 'form-control form-control-sm', 'style': 'width:200px;'}),
                                                           'credit': CheckboxInput(attrs={'class': 'form-control form-control-sm', 'style': 'width:15px; margin:auto;'}),
                                                           'currency': Select(attrs={'class': 'form-control form-control-sm', 'style': 'width:67px; margin:auto;'}),
                                                           'active': CheckboxInput(attrs={'class': 'form-control form-control-sm', 'style': 'width:15px; margin:auto;'})})

            context['threshold_formset'] = ThresholdFormSet()

            context['account_formset'] = AccountFormSet()

            context['recurring_list'] = Recurring.objects.filter(user=user_object).values('name', 'type', 'account__account', 'category__category', 'active', 'amount')
            context['recurring_form'] = RecurringForm()

            context['quick_entry_list'] = QuickEntry.objects.filter(user=user_object).values('id', 'category__category', 'item', 'amount', 'category_2__category', 'amount_2', 'description')
            context['quick_entry_form'] = QuickEntryForm()

            profile_form_data = {'account_to_use': user_object.profile.account_to_use.id if user_object.profile.account_to_use is not None else None,
                                 'second_account_to_use': user_object.profile.second_account_to_use.id if user_object.profile.second_account_to_use is not None else None,
                                 'third_account_to_use': user_object.profile.third_account_to_use.id if user_object.profile.third_account_to_use is not None else None,
                                 'credit_account': user_object.profile.credit_account.id if user_object.profile.credit_account is not None else None,
                                 'debit_account': user_object.profile.debit_account.id if user_object.profile.debit_account is not None else None,
                                 'primary_currency': user_object.profile.primary_currency, }

            context['profile_form'] = ProfileForm(profile_form_data)

            context['purchase_category_count'] = PurchaseCategory.objects.filter(user=user_object).count()
            context['account_count'] = Account.objects.filter(user=user_object).count()
            context['recurring_count'] = Recurring.objects.filter(user=user_object).count()
            context['quick_entry_count'] = QuickEntry.objects.filter(user=user_object).count()

            return render(request, 'tracker/settings.html', context=context)


    elif request.method == 'POST':
        data_dict = {}
        # print(request.POST)
        if request.POST['type'] == 'Submit':
            if request.POST['model'] == 'Quick Entry':
                quick_entry_form = QuickEntryForm(request.POST)

                if quick_entry_form.is_valid():
                    quick_entry_instance = QuickEntry()

                    quick_entry_instance.user = user_object
                    quick_entry_instance.item = quick_entry_form.cleaned_data['item'].strip()
                    quick_entry_instance.category = quick_entry_form.cleaned_data['category']
                    quick_entry_instance.amount = quick_entry_form.cleaned_data['amount']
                    quick_entry_instance.category_2 = quick_entry_form.cleaned_data['category_2']
                    quick_entry_instance.amount_2 = quick_entry_form.cleaned_data['amount_2']
                    quick_entry_instance.description = quick_entry_form.cleaned_data['description'].strip() if len(quick_entry_form.cleaned_data['description'].strip()) == 0 or quick_entry_form.cleaned_data['description'].strip()[-1] == '.' else quick_entry_form.cleaned_data['description'].strip() + '.' # Add a period if not present

                    quick_entry_instance.save()

            elif request.POST['model'] == 'Recurring Payment':
                    recurring_instance = Recurring()

                    recurring_instance.user = user_object
                    recurring_instance.name = request.POST['name'].strip()
                    recurring_instance.description = request.POST['description'].strip()
                    recurring_instance.type = request.POST['recurring_type']
                    recurring_instance.account = Account.objects.get(id=request.POST['account'])
                    recurring_instance.category = PurchaseCategory.objects.get(id=request.POST['category'])
                    recurring_instance.active = True if request.POST['active'] == 'true' else False
                    recurring_instance.amount = request.POST['amount']
                    recurring_instance.start_date = request.POST['start_date']
                    recurring_instance.dates = request.POST['dates']
                    recurring_instance.weekdays = request.POST['weekdays']
                    recurring_instance.number = None if request.POST['number'] == '' else request.POST['number']
                    recurring_instance.interval_type = request.POST['interval_type']
                    recurring_instance.xth_type = request.POST['xth_type']
                    recurring_instance.xth_from_specific_date = request.POST['xth_from_specific_date']
                    recurring_instance.xth_after_months = None if request.POST['xth_after_months'] == '' else request.POST['xth_after_months']

                    recurring_instance.save()

        elif request.POST['type'] == 'Delete': # ALL ARE TRIMMED in the front-end!
            if request.POST['model'] == 'Purchase Category':
                to_delete = PurchaseCategory.objects.filter(user=user_object, category=request.POST['to_delete'])
            elif request.POST['model'] == 'Account':
                to_delete = Account.objects.filter(user=user_object, account=request.POST['to_delete'])
            elif request.POST['model'] == 'Recurring Payment':
                to_delete = Recurring.objects.filter(user=user_object, name=request.POST['to_delete'])
            elif request.POST['model'] == 'Quick Entry':
                to_delete = QuickEntry.objects.filter(user=user_object, id=request.POST['to_delete'])

            # Filter will always run, so throw an error if no items to delete were found
            if to_delete.count() > 0:
                to_delete.delete()
            else:
                raise Exception('No items to delete!')

        elif request.POST['type'] == 'Update':
            if request.POST['model'] == 'Profile':
                if request.POST['value'].isdigit(): # request.POST['value'] is a string
                    setattr(user_object.profile, request.POST['id'][3:], Account.objects.get(id=request.POST['value']))
                else:
                    setattr(user_object.profile, request.POST['id'][3:], None if request.POST['value'] == '' else request.POST['value'])
                user_object.save()

            elif request.POST['model'] == 'Purchase Category':
                if request.POST['id'] == '': # This is the bottom, blank row. Won't have an ID, so create a new object
                    purchase_category_object = PurchaseCategory.objects.create(user=user_object)
                    data_dict.update({'id': purchase_category_object.id})
                else: # Otherwise, get the PurchaseCategory and update the appropriate attribute
                    purchase_category_object = PurchaseCategory.objects.get(id=request.POST['id'])
                if request.POST['field'] == 'threshold':
                    value = Decimal(request.POST['value'])
                elif request.POST['field'] == 'threshold_rolling_days':
                    value = int(request.POST['value'])
                else: # Field is 'category'
                    value = request.POST['value']
                setattr(purchase_category_object, request.POST['field'], value)
                purchase_category_object.save()

            elif request.POST['model'] == 'Account':
                if request.POST['id'] == '':
                    account_object = Account.objects.create(user=user_object)
                    data_dict.update({'id': account_object.id})
                else:
                    account_object = Account.objects.get(id=request.POST['id'])

                if request.POST['field'] == 'account':
                    value = request.POST['value']
                elif request.POST['field'] == 'credit': # .val() comes through as 'on' for checkboxes. Use .is(':checked') ... but easier to toggle here
                    value = not(account_object.credit)
                elif request.POST['field'] == 'currency':
                    value = request.POST['value']
                else: # Field is 'active'
                    value = not(account_object.active)
                setattr(account_object, request.POST['field'], value)
                account_object.save()

            elif request.POST['model'] == 'Recurring Payment':
                recurring_queryset = Recurring.objects.filter(name=request.POST['name'])
                for object in recurring_queryset:
                    if object.active:
                        object.active = False
                    else:
                        object.active = True
                    object.save()

            return JsonResponse(data_dict) # Only needed for update, to return an ID of the row for Purchase Category and Account
        return HttpResponse()


@login_required
def filter_manager(request):
    user_object = request.user

    if request.method == 'GET' and request.GET['page'] == 'Activity' or request.method == 'POST' and request.POST['page'] == 'Activity': # GET must be first!
        filter_instance = Filter.objects.get(user=user_object, page='Activity')
    else:
        filter_instance = Filter.objects.get(user=user_object, page='Homepage')

    if request.method == 'POST' and request.POST['type'] != 'Date' or request.method == 'GET': # We need these for any GET request, and obviously not for POST requests for the date filters
        # Generate a comprehensive list of PurchaseCategories
        full_category_filter_list = []
        for purchase_category in PurchaseCategory.objects.filter(user=user_object):
            full_category_filter_list.append(purchase_category.category)
        full_category_filter_list.sort()
        print('Full category filter list: ' + str(full_category_filter_list))

        # Extract the current filter values
        category_filter_1 = filter_instance.category_filter_1; category_filter_2 = filter_instance.category_filter_2
        category_filter_3 = filter_instance.category_filter_3; category_filter_4 = filter_instance.category_filter_4
        category_filter_5 = filter_instance.category_filter_5; category_filter_6 = filter_instance.category_filter_6
        category_filter_7 = filter_instance.category_filter_7; category_filter_8 = filter_instance.category_filter_8
        category_filter_9 = filter_instance.category_filter_9; category_filter_10 = filter_instance.category_filter_10
        category_filter_11 = filter_instance.category_filter_11; category_filter_12 = filter_instance.category_filter_12
        category_filter_13 = filter_instance.category_filter_13; category_filter_14 = filter_instance.category_filter_14
        category_filter_15 = filter_instance.category_filter_15; category_filter_16 = filter_instance.category_filter_16
        category_filter_17 = filter_instance.category_filter_17; category_filter_18 = filter_instance.category_filter_18
        category_filter_19 = filter_instance.category_filter_19; category_filter_20 = filter_instance.category_filter_20
        category_filter_21 = filter_instance.category_filter_21; category_filter_22 = filter_instance.category_filter_22
        category_filter_23 = filter_instance.category_filter_23; category_filter_24 = filter_instance.category_filter_24
        category_filter_25 = filter_instance.category_filter_25

        # Make a list of the currently applied filters
        current_filter_list = [x.category if x is not None else x for x in [category_filter_1, category_filter_2, category_filter_3, category_filter_4, category_filter_5, category_filter_6, category_filter_7, category_filter_8, category_filter_9, category_filter_10,
                       category_filter_11, category_filter_12, category_filter_13, category_filter_14, category_filter_15, category_filter_16, category_filter_17, category_filter_18, category_filter_19, category_filter_20,
                       category_filter_21, category_filter_22, category_filter_23, category_filter_24, category_filter_25]]
        current_filter_list_unique = sorted(list(set([x for x in current_filter_list if x])))
        print('Originally applied filters: ' + str(current_filter_list_unique))

    if request.method == 'GET': # DATE FILTER VALUES ARE SENT IN homepage() and PurchaseListView() ! No need here.
        if len(current_filter_list_unique) == len(full_category_filter_list):
            current_filter_list_unique.append('All Categories')
        return JsonResponse(current_filter_list_unique, safe=False)

    if request.method == 'POST':
        # Get the filter that was clicked
        filter_value = request.POST['id'] # The filter 'value' is simply stored in the ID
        print('Clicked filter value: ' + str(filter_value))

        if request.POST['type'] == 'Date':
            filter_value = request.POST['filter_value'] # Only present in date-related AJAX calls

            if filter_value == '':
                filter_value = None

            if request.POST['id'] == 'datepicker':
                filter_instance.start_date_filter = filter_value
            elif request.POST['id'] == 'datepicker_2':
                filter_instance.end_date_filter = filter_value

            filter_instance.save()

            return HttpResponse()

        elif request.POST['type'] == 'Category':

            def set_filters(filter_list):
                reset_filters()

                try:
                    filter_instance.category_filter_1 = None if filter_list[0] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[0])
                    filter_instance.category_filter_2 = None if filter_list[1] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[1])
                    filter_instance.category_filter_3 = None if filter_list[2] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[2])
                    filter_instance.category_filter_4 = None if filter_list[3] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[3])
                    filter_instance.category_filter_5 = None if filter_list[4] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[4])
                    filter_instance.category_filter_6 = None if filter_list[5] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[5])
                    filter_instance.category_filter_7 = None if filter_list[6] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[6])
                    filter_instance.category_filter_8 = None if filter_list[7] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[7])
                    filter_instance.category_filter_9 = None if filter_list[8] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[8])
                    filter_instance.category_filter_10 = None if filter_list[9] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[9])
                    filter_instance.category_filter_11 = None if filter_list[10] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[10])
                    filter_instance.category_filter_12 = None if filter_list[11] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[11])
                    filter_instance.category_filter_13 = None if filter_list[12] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[12])
                    filter_instance.category_filter_14 = None if filter_list[13] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[13])
                    filter_instance.category_filter_15 = None if filter_list[14] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[14])
                    filter_instance.category_filter_16 = None if filter_list[15] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[15])
                    filter_instance.category_filter_17 = None if filter_list[16] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[16])
                    filter_instance.category_filter_18 = None if filter_list[17] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[17])
                    filter_instance.category_filter_19 = None if filter_list[18] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[18])
                    filter_instance.category_filter_20 = None if filter_list[19] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[19])
                    filter_instance.category_filter_21 = None if filter_list[20] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[20])
                    filter_instance.category_filter_22 = None if filter_list[21] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[21])
                    filter_instance.category_filter_23 = None if filter_list[22] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[22])
                    filter_instance.category_filter_24 = None if filter_list[23] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[23])
                    filter_instance.category_filter_25 = None if filter_list[24] is None else PurchaseCategory.objects.get(user=user_object, category=filter_list[24])
                except: # If list passed in is not long enough...
                    pass

                filter_instance.save()

            def reset_filters():
                filter_instance.category_filter_1 = None; filter_instance.category_filter_2 = None; filter_instance.category_filter_3 = None
                filter_instance.category_filter_4 = None; filter_instance.category_filter_5 = None; filter_instance.category_filter_6 = None
                filter_instance.category_filter_7 = None; filter_instance.category_filter_8 = None; filter_instance.category_filter_9 = None
                filter_instance.category_filter_10 = None; filter_instance.category_filter_11 = None; filter_instance.category_filter_12 = None
                filter_instance.category_filter_13 = None; filter_instance.category_filter_14 = None; filter_instance.category_filter_15 = None
                filter_instance.category_filter_16 = None; filter_instance.category_filter_17 = None; filter_instance.category_filter_18 = None
                filter_instance.category_filter_19 = None; filter_instance.category_filter_20 = None; filter_instance.category_filter_21 = None
                filter_instance.category_filter_22 = None; filter_instance.category_filter_23 = None; filter_instance.category_filter_24 = None
                filter_instance.category_filter_25 = None

                filter_instance.save()


            # Clear filter values if necessary
            if filter_value == 'All Categories':
                reset_filters()
                if len(current_filter_list_unique) == len(full_category_filter_list) or len(current_filter_list_unique) == 25: # For when you've just clicked 'All Categories'
                    return JsonResponse([], safe=False) # safe=False necessary for non-dict objects to be serialized
                else:
                    set_filters(full_category_filter_list)
                    if len(full_category_filter_list) < 26:
                        full_category_filter_list.append('All Categories')
                    return JsonResponse(full_category_filter_list, safe=False) # safe=False necessary for non-dict objets to be serialized

            else:
                if len(current_filter_list_unique) == 25: # Otherwise, there's an available slot...
                    reset_filters()
                    return JsonResponse([], safe=False) # safe=False necessary for non-dict objects to be serialized

                else:
                    if filter_value in current_filter_list_unique:
                        current_filter_list_unique.remove(filter_value)
                    else:
                        current_filter_list_unique.append(filter_value)

                    current_filter_list_unique.sort()
                    print('New applied filter list: ' + str(current_filter_list_unique))

                    set_filters(current_filter_list_unique)

                    if len(current_filter_list_unique) == len(full_category_filter_list):
                        current_filter_list_unique.append('All Categories')

                    return JsonResponse(current_filter_list_unique, safe=False) # safe=False necessary for non-dict objects to be serialized


# @login_required
# def mode_manager(request):
#     if request.method == 'GET':
#         mode_instance = Mode.objects.last()
#
#         if mode_instance is None:
#             mode_instance = Mode.objects.create(mode='All')
#
#         return JsonResponse( {'mode': mode_instance.mode} )
#
#     elif request.method == 'POST':
#         mode_instance = Mode.objects.last()
#         mode_instance.mode = request.POST['mode']
#         mode_instance.save()
#
#         return HttpResponse()
