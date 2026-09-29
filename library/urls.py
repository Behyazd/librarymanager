from django.urls import path
from . import views

app_name = 'library'

urlpatterns = [
    path('', views.BookListView.as_view(), name='book_list'),
    path('books/<int:pk>/', views.book_detail, name='book_detail'),
    path('books/add/', views.book_add, name='book_add'),
    path('books/<int:pk>/edit/', views.book_edit, name='book_edit'),
    path('books/search/', views.book_search_online, name='book_search'),
    path('books/import/', views.book_import, name='book_import'),
    path('books/advanced-search/', views.advanced_search, name='advanced_search'),
    path('books/<int:book_pk>/loan/', views.loan_create, name='loan_create'),
    path('books/<int:pk>/upload-cover/', views.upload_cover, name='upload_cover'),
    path('books/<int:pk>/delete-cover/', views.delete_cover, name='delete_cover'),
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/<int:pk>/return/', views.loan_return, name='loan_return'),
    path('loans/<int:pk>/extend/', views.loan_extend, name='loan_extend'),
    path('members/', views.member_list, name='member_list'),
    path('members/<int:pk>/', views.member_detail, name='member_detail'),
    path('reports/', views.reports, name='reports'),
    path('reports/books/', views.report_books, name='report_books'),
    path('reports/available-books/', views.report_available_books, name='report_available_books'),
    path('reports/members/', views.report_members, name='report_members'),
    path('reports/active-loans/', views.report_active_loans, name='report_active_loans'),
    path('reports/overdue-loans/', views.report_overdue_loans, name='report_overdue_loans'),
    path('api/autocomplete/books/', views.autocomplete_books, name='autocomplete_books'),

    # Export
    path('export/books/excel/', views.export_books_excel, name='export_books_excel'),
    path('export/books/pdf/', views.export_books_pdf, name='export_books_pdf'),
    path('export/labels/pdf/', views.export_labels_pdf, name='export_labels_pdf'),
    path('print-labels/', views.print_labels, name='print_labels'),

# در library/urls.py
    path('print-spines/', views.print_spines, name='print_spines'),
    path('export/spines/pdf/', views.export_spine_pdf, name='export_spine_pdf'),
]