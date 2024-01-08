""" Views for tabs 'Settings of securities', 'Candles', 'Returns'."""
import datetime
import logging
from typing import Any
import celery.result
import celery.states
from django.core.paginator import Paginator
import django.db.models as dj_models
import django.db.utils as dj_db_utils
from django.http import HttpResponseRedirect, JsonResponse
from django.http.request import HttpRequest
from django.http.response import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from django.contrib import messages as dj_messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from app.redis_app import redisApp
from . import models, forms, download, tasks

POST = 'POST'
MENU_SECTION_SETTINGS = 'SecuritySettings'

logger = logging.getLogger('custom_debug')


def removeUnusedFetchedData(fetchedDataPks: list) -> None:
    """ Remove all models.FetchedData objects with id from fetchedDataPks
        that aren't used in usersecurityfetchsetting db table.
    Args:
        fetchedDataPks (list): primary keys of models.FetchedData objects
    """
    fetchedDataPks = [pk for pk in fetchedDataPks if pk]
    if not fetchedDataPks:
        return
    res = models.FetchedData.objects.filter(
        pk__in=fetchedDataPks, usersecurityfetchsetting__isnull=True).only('pk').delete()
    logger.debug(f'Removed FetchedData objs: {res}')


class Messages:
    """ Hints to user."""
    EDIT_SUCCESS = _('The changes were saved successfully')
    EDIT_ERROR = _('Errors occurred during the update')
    ADD_SUCCESS = _('The operation was successful')
    ADD_ERROR = _('Errors occurred during the operation')
    DELETE_SUCCESS = ADD_SUCCESS
    CREATE_TASK_SUCCESS = _('The task was successfully created')
    SETTING_EXIST = _('Settings with the same parameters #1 - #5 already exist.')


class SecuritySettingListView(LoginRequiredMixin, ListView):
    """ View for displaying ... """
    template_name = 'securitySettings/list.html'
    context_object_name = 'securitySettings'
    model = models.UserSecurityFetchSetting
    ordering = ('sequence_number',)

    MENU_SECTION = MENU_SECTION_SETTINGS

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """ Add object_list to the context, generate response.
        Args:
            request (HttpRequest): user request
        Returns:
            HttpResponse: response for user
        """
        self.__request = request
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> dj_models.query.QuerySet:
        queryset = self.__class__.model.objects.filter(user_id=self.__request.user)\
            .prefetch_related(models.FetchedData.getPrefetchObjWoDataFields())
        ordering = self.get_ordering()
        if ordering:
            queryset = queryset.order_by(*ordering)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """ Collect additional data for displaying the list of objects.
        Returns:
            dict[str, Any]: context data
        """
        context = super().get_context_data(**kwargs)
        context['section'] = self.__class__.MENU_SECTION
        return context


@login_required
def createSecuritySetting(request: HttpRequest) -> HttpResponse:
    """ View for creation of models.UserSecurityFetchSetting objects using
        several different forms as one large form.
    """
    template_name = 'securitySettings/create.html'
    success_url = reverse_lazy('candles:settingList')
    MENU_SECTION = MENU_SECTION_SETTINGS

    if request.method == POST:
        security_form = forms.SecurityForm(request.POST)
        fetchSetting_form = forms.FetchSettingForm(request.POST)
        userSecuritySettings_form = forms.UserSecuritySettingsForm(request.POST)

        if security_form.is_valid() and fetchSetting_form.is_valid() and \
                userSecuritySettings_form.is_valid():
            security, __ = models.Security.objects.get_or_create(
                **security_form.cleaned_data)
            fetch_setting, __ = models.FetchSetting.objects.get_or_create(
                **fetchSetting_form.cleaned_data)
            fetched_data, __ = models.FetchedData.objects\
                .only('security', 'fetch_setting').get_or_create(
                    security=security, fetch_setting=fetch_setting)

            maxSeqNum = models.UserSecurityFetchSetting.objects.filter(user=request.user)\
                .aggregate(maxSeqNum=dj_models.Max('sequence_number')).get('maxSeqNum') or 0

            userSecuritySettings_form.instance.user = request.user
            userSecuritySettings_form.instance.fetched_data = fetched_data
            userSecuritySettings_form.instance.sequence_number = maxSeqNum + 1
            userSecuritySettings_form.instance.has_error = None

            try:
                userSecuritySettings_form.save()
            except dj_db_utils.IntegrityError:
                dj_messages.error(request, Messages.SETTING_EXIST)
            else:
                dj_messages.success(request, Messages.ADD_SUCCESS)
                return HttpResponseRedirect(success_url)
        else:
            dj_messages.error(request, Messages.ADD_ERROR)
    else:
        security_form = forms.SecurityForm()
        fetchSetting_form = forms.FetchSettingForm()
        userSecuritySettings_form = forms.UserSecuritySettingsForm()

    return render(request, template_name,
                  {'security_form': security_form, 'fetchSetting_form': fetchSetting_form,
                   'userSecuritySettings_form': userSecuritySettings_form,
                   'section': MENU_SECTION})


@login_required
def updateSecuritySetting(request: HttpRequest, pk: int) -> HttpResponse:
    """ View for updating models.UserSecurityFetchSetting objects using
        several different forms as one large form."""
    template_name = 'securitySettings/update.html'
    success_url = reverse_lazy('candles:settingList')
    model = models.UserSecurityFetchSetting
    MENU_SECTION = MENU_SECTION_SETTINGS

    obj = get_object_or_404(model, pk=pk, user=request.user)
    security = obj.fetched_data.security
    fetch_setting = obj.fetched_data.fetch_setting

    if request.method == POST:
        security_form = forms.SecurityForm(instance=security, data=request.POST)
        fetchSetting_form = forms.FetchSettingForm(instance=fetch_setting, data=request.POST)
        userSecuritySettings_form = forms.UserSecuritySettingsForm(instance=obj, data=request.POST)

        prevFetchedDataPk = None
        if security_form.is_valid() and fetchSetting_form.is_valid() and \
                userSecuritySettings_form.is_valid():
            if security_form.has_changed() or fetchSetting_form.has_changed():
                if security_form.has_changed():
                    security, __ = models.Security.objects.get_or_create(
                        **security_form.cleaned_data)
                if fetchSetting_form.has_changed():
                    fetch_setting, __ = models.FetchSetting.objects.get_or_create(
                        **fetchSetting_form.cleaned_data)

                fetched_data, __ = models.FetchedData.objects.only('security', 'fetch_setting')\
                    .get_or_create(security=security, fetch_setting=fetch_setting)

                prevFetchedDataPk = obj.fetched_data.pk
                userSecuritySettings_form.instance.fetched_data = fetched_data
                userSecuritySettings_form.instance.has_error = None
            try:
                userSecuritySettings_form.save()
            except dj_db_utils.IntegrityError:
                dj_messages.error(request, Messages.SETTING_EXIST)
            else:
                removeUnusedFetchedData([prevFetchedDataPk])
                dj_messages.success(request, Messages.EDIT_SUCCESS)
                return HttpResponseRedirect(success_url)
        else:
            dj_messages.error(request, Messages.EDIT_ERROR)
    else:
        security_form = forms.SecurityForm(instance=security)
        fetchSetting_form = forms.FetchSettingForm(instance=fetch_setting)
        userSecuritySettings_form = forms.UserSecuritySettingsForm(instance=obj)

    return render(request, template_name,
                  {'security_form': security_form, 'fetchSetting_form': fetchSetting_form,
                   'userSecuritySettings_form': userSecuritySettings_form,
                   'section': MENU_SECTION})


@login_required
def chooseAction(request: HttpRequest) -> HttpResponse:
    """ Call another view function depending on pressed button."""
    if request.method == POST:
        if request.POST.get('delete', None):
            return bulkDelete(request)
        if request.POST.get('setOrdering', None):
            return setOrdering(request)
    return HttpResponseBadRequest()


@login_required
def bulkDelete(request: HttpRequest) -> HttpResponse:
    """ View for removal of several or all model objects."""
    model = models.UserSecurityFetchSetting
    templateName = 'securitySettings/bulk_delete_confirm.html'
    itemName = 'list-group-item'
    MENU_SECTION = MENU_SECTION_SETTINGS

    if request.method == POST:
        itemIds = request.POST.getlist(itemName)
        nextAfterConfirmatn = request.POST.get('next_next', '/')
        deleteOption = request.POST.get('delete')

        if deleteOption == 'selected':
            items = model.objects.filter(id__in=itemIds, user=request.user)
        elif deleteOption == 'all':
            items = model.objects.filter(user=request.user)
        else:
            return HttpResponseBadRequest()

        items = items.prefetch_related(models.FetchedData.getPrefetchObjWoDataFields())
        return render(request, templateName,
                      {'items': items, 'next': nextAfterConfirmatn, 'section': MENU_SECTION})

    return HttpResponseBadRequest()


@login_required
def setOrdering(request: HttpRequest) -> HttpResponse:
    """ View for setting ordering of model objects."""
    model = models.UserSecurityFetchSetting
    itemName = 'list-ordering-item'

    if request.method == POST:

        setOrderingInp = request.POST.get('setOrdering', None)
        if not setOrderingInp or setOrderingInp != 'set':
            return HttpResponseBadRequest()

        seqNums = request.POST.getlist(itemName)
        renameDict = {int(seqNum): i for seqNum, i in zip(seqNums, range(1, len(seqNums) + 1))
                      if int(seqNum) != i}
        items = model.objects.filter(user=request.user)
        itemsSeqNums = items.values_list('sequence_number', flat=True)

        for i, item in enumerate(items):
            newVal = renameDict.get(itemsSeqNums[i], None)
            if newVal:
                item.sequence_number = newVal
        model.objects.bulk_update(items, ['sequence_number'])

        return HttpResponseRedirect(reverse_lazy('candles:settingList'))

    return HttpResponseBadRequest()


@login_required
def bulkDeleteConfirm(request: HttpRequest) -> HttpResponse:
    """ View for confirmation of model objects removal."""
    model = models.UserSecurityFetchSetting
    itemName = 'list-group-item'

    if request.method == POST:
        items = request.POST.getlist(itemName)
        next_ = request.POST.get('next', '/')
        qs = model.objects.filter(id__in=items, user=request.user)
        ids = qs.values_list('fetched_data_id', flat=True)[::1]
        logger.debug(f'Removed UserSecurityFetchSetting objs: {qs.delete()}')
        removeUnusedFetchedData(ids)
        dj_messages.success(request, Messages.DELETE_SUCCESS)
        return HttpResponseRedirect(next_)

    return HttpResponseBadRequest()


@login_required
def addStocksTopByCap(request: HttpRequest) -> HttpResponse:
    """ View to add N top stocks by capitalization."""
    NUM_TOP_CAPITALIZATN_STOCKS = 150

    if request.method == POST:
        wereAdded = models.UserSecurityFetchSetting.addStocksNumTopCap(
            user=request.user, numTop=NUM_TOP_CAPITALIZATN_STOCKS)
        if wereAdded:
            dj_messages.success(request, Messages.ADD_SUCCESS)
        else:
            dj_messages.error(request, Messages.ADD_ERROR)
        return HttpResponseRedirect(reverse_lazy('candles:settingList'))

    return HttpResponseBadRequest()


@login_required
def getCandlesPreview(request: HttpRequest) -> HttpResponse:
    """ View with base candle template without OHLCV data and charts."""
    template_name = 'candles/list.html'
    MENU_SECTION = 'candles'

    return render(request, template_name, {'section': MENU_SECTION})


@login_required
def getCandles(request: HttpRequest) -> HttpResponse:
    """ View to load OHLCV data load from DB and fetch too old data from MOEX."""
    template_name = 'candles/charts.html'
    numObjsPerPage = 50
    FETCH_TIMEOUT = 300

    objs = models.UserSecurityFetchSetting.objects.filter(
        user=request.user).order_by('sequence_number')

    ids = request.GET.get('ids')
    if ids:
        # load objs from DB with specified fetched_data 'ids'

        ids = [int(id_) for id_ in ids.split(',')]
        preserved = dj_models.Case(*[dj_models.When(fetched_data_id=id_, then=position)
                                     for position, id_ in enumerate(ids)])
        objs = objs.select_related('fetched_data__security').filter(fetched_data_id__in=ids)\
            .order_by(preserved)

        paginator = Paginator(objs, numObjsPerPage)
        pageNum = request.GET.get('page')
        page = paginator.get_page(pageNum)
        pageObjs = page.object_list

        results = [obj.fetched_data.data for obj in pageObjs]
        securities = [obj.fetched_data.security.security for obj in pageObjs]

        return JsonResponse({'html': render_to_string(
            template_name, {'objects': range(len(results)), 'page_obj': page}, request),
            'jsonObjects': results, 'titles': securities})

    paginator = Paginator(objs, numObjsPerPage)
    pageNum = request.GET.get('page')
    page = paginator.get_page(pageNum)
    pageObjs = page.object_list

    pageObjs = pageObjs.select_related('fetched_data__security', 'fetched_data__fetch_setting')
    pageUrls = [obj.fetched_data.getURL() for obj in pageObjs]
    pageTitles = [obj.fetched_data.security.security for obj in pageObjs]

    # Extract json files from DB if they aren't too old
    pageObjsDB = {
        pageUrls[i]: obj.fetched_data.data
        for i, obj in enumerate(pageObjs)
        if obj.fetched_data.data_update_dt and
        timezone.now() - obj.max_update_rate < obj.fetched_data.data_update_dt
    }

    pageUrlsToGet = list(set(pageUrls) - set(pageObjsDB.keys()))
    if pageUrlsToGet:
        newDataArrs, statuses, errors, errRespUrls, beginDts, endDts, isFulls = \
            download.MOEX_Downloader.fetchData(pageUrlsToGet, FETCH_TIMEOUT)
    else:
        newDataArrs, errRespUrls = [], []

    # Add to DB information about not successful requests
    models.CandlesUpdate.objects.bulk_create([
        models.CandlesUpdate(url=url, status=statuses[i], error=errors[i])
        for i, url in enumerate(errRespUrls)
    ])
    errRespUrls = set(errRespUrls)

    results = [pageObjsDB.get(url, None) or newDataArrs[pageUrlsToGet.index(url)]
               for url in pageUrls
               if url not in errRespUrls]

    # Add successful fetched json files to DB
    objsToUpd = []
    for i, arr in enumerate(newDataArrs):
        if pageUrlsToGet[i] not in errRespUrls:
            j = pageUrls.index(pageUrlsToGet[i])
            pageObjs[j].fetched_data.data = arr
            pageObjs[j].fetched_data.data_update_dt = timezone.now()
            pageObjs[j].fetched_data.data_first_dt = beginDts[i]
            pageObjs[j].fetched_data.data_last_dt = endDts[i]
            pageObjs[j].fetched_data.data_is_full = isFulls[i]
            objsToUpd.append(pageObjs[j].fetched_data)
    models.FetchedData.objects.bulk_update(
        objsToUpd, ['data', 'data_update_dt', 'data_first_dt', 'data_last_dt', 'data_is_full'])

    # Add info about possibly erroneous settings to DB
    objsToUpd = []
    for url in pageUrlsToGet:
        i = pageUrls.index(url)
        if url in errRespUrls:
            pageObjs[i].has_error = True
        else:
            pageObjs[i].has_error = False
        objsToUpd.append(pageObjs[i])
    models.UserSecurityFetchSetting.objects.bulk_update(objsToUpd, ['has_error'])

    return JsonResponse({'html': render_to_string(
        template_name, {'objects': range(len(results)), 'page_obj': page}, request),
        'jsonObjects': results, 'titles': pageTitles})


@login_required
def returnsTask(request: HttpRequest) -> HttpResponse:
    """ View for creation returns task and displaying its results."""
    template_name_create = 'candles/return_task_create.html'
    template_name_results = 'candles/return_task_results.html'
    MENU_SECTION = 'returns'
    REDIS_RESULT_EXPIRES = datetime.timedelta(hours=6)  # it should be < CELERY_RESULT_EXPIRES

    celeryTasks = redisApp.hgetall(f'users:{request.user.id}:returnTasks')
    if celeryTasks:
        taskId, taskParams = celeryTasks.popitem()
        asyncResult = celery.result.AsyncResult(id=taskId)
        taskState = asyncResult.state
        taskParams = taskParams.decode('utf-8')
        if taskState in {celery.states.REVOKED, celery.states.FAILURE}:
            redisApp.hdel(f'users:{request.user.id}:returnTasks', taskId)
            return render(request, template_name_results,
                          {'section': MENU_SECTION, 'failed': True, 'inProgress': False,
                           'taskParams': taskParams, 'longReturns': [], 'shortReturns': []})

        if taskState == celery.states.SUCCESS:
            longReturns, shortReturns, longIds, shortIds, orderingInd = asyncResult.get()
            redisApp.hdel(f'users:{request.user.id}:returnTasks', taskId)
            return render(request, template_name_results,
                          {'section': MENU_SECTION, 'taskParams': taskParams,
                           'failed': False, 'inProgress': False,
                           'longReturns': longReturns, 'shortReturns': shortReturns,
                           'longIds': longIds, 'shortIds': shortIds, 'orderingInd': orderingInd})

        # state is in {PENDING, RECEIVED, RETRY, STARTED}
        return render(request, template_name_results,
                      {'section': MENU_SECTION, 'failed': False, 'inProgress': True,
                       'taskParams': taskParams, 'longReturns': [], 'shortReturns': []})

    if request.method == POST:
        taskForm = forms.ReturnsTaskForm(request.POST)
        if taskForm.is_valid():
            cd = taskForm.cleaned_data
            cd['duration'] = int(cd['duration'].total_seconds())
            asyncResult = tasks.findBestReturnsForAllSecurities.apply_async(args=(cd,))
            taskParams = taskForm.cleanedDataAsStr()
            redisApp.hset(f'users:{request.user.id}:returnTasks',
                          mapping={asyncResult.task_id: taskParams})
            redisApp.expire(f'users:{request.user.id}:returnTasks', REDIS_RESULT_EXPIRES)
            dj_messages.success(request, Messages.CREATE_TASK_SUCCESS)
            return render(request, template_name_results,
                          {'section': MENU_SECTION, 'failed': False, 'inProgress': True,
                           'taskParams': taskParams, 'longReturns': [], 'shortReturns': []})

        dj_messages.error(request, Messages.ADD_ERROR)
    else:
        taskForm = forms.ReturnsTaskForm()
    return render(request, template_name_create, {'section': MENU_SECTION, 'task_form': taskForm})
