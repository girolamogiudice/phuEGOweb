from py4web import DAL, Field
from pydal.validators import IS_IN_SET, IS_STRONG
from .common import db
from .app_config import available_network_names, default_network_name


NETWORK_CHOICES = available_network_names()
DEFAULT_NETWORK = default_network_name()
KDE_PROBABILITY_CHOICES = ['Optimal','0.5','0.55','0.6','0.65','0.7','0.75','0.80','0.85','0.9','0.95']

db.define_table(
    'submissions',
    Field('protein_lfc_text', 'text', label='Phosphoprotein LFC'),
    Field('network_type', requires=IS_IN_SET(NETWORK_CHOICES), default=DEFAULT_NETWORK, label='Network'),
    Field('first_propagation', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='First Propagation Damping'),
    Field('first_propagation_significance', 'double', requires=IS_IN_SET([0.01,0.05,0.1]), default=0.05, label='First Propagation Significance'),
    Field('kde_probability',requires=IS_IN_SET(KDE_PROBABILITY_CHOICES,zero=None),default='0.85',label='KDE probability'),
    Field('zscore', 'double', requires=IS_IN_SET([1.04,1.28,1.64,2.33]), default=1.64, label='Zscore Semantic Similarity'),
    Field('second_propagation_damping', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='Second Propagation Damping'),
    Field('minimum_ego_nodes', 'double', requires=IS_IN_SET([i for i in range(1, 10, 1)]), default=5, label='Minimum Ego Nodes'),
    Field('third_propagation_damping', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='Third Propagation Damping'),
    Field('fisher_significance', 'double', requires=IS_IN_SET([0.01,0.05,0.1]), default=0.05, label='Fisher Significance'),
    migrate=True
)


db.define_table(
    'uuid_mapping',
    Field('form_id', 'integer'),
    Field('uuid', 'string', length=36),
    migrate=True
)


db.define_table(
    'scsubmissions',
    Field('lfc_text', 'text', label='Gene/Uniprot LFC'),
    Field('network_type', requires=IS_IN_SET(NETWORK_CHOICES), default=DEFAULT_NETWORK, label='Network'),
    Field('first_propagation', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='First Propagation Damping'),
    Field('first_propagation_significance', 'double', requires=IS_IN_SET([0.01,0.05,0.1]), default=0.05, label='First Propagation Significance'),
    Field('kde_probability',requires=IS_IN_SET(KDE_PROBABILITY_CHOICES,zero=None),default='0.85',label='KDE probability'),
    Field('zscore', 'double', requires=IS_IN_SET([1.04,1.28,1.64,2.33]), default=1.64, label='Zscore Semantic Similarity'),
    Field('second_propagation_damping', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='Second Propagation Damping'),
    Field('minimum_ego_nodes', 'double', requires=IS_IN_SET([i for i in range(1, 10, 1)]), default=5, label='Minimum Ego Nodes'),
    Field('third_propagation_damping', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='Third Propagation Damping'),
    Field('fisher_significance', 'double', requires=IS_IN_SET([0.01,0.05,0.1]), default=0.05, label='Fisher Significance'),

    migrate=True
)

db.define_table(
    'custom_submissions',
    Field('protein_lfc_text', 'text', label='Uniprot/Gene LFC'),
    Field('network_type', requires=IS_IN_SET(NETWORK_CHOICES), default=DEFAULT_NETWORK, label='Network'),
    Field('first_propagation', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='First Propagation Damping'),
    Field('first_propagation_significance', 'double', requires=IS_IN_SET([0.01,0.05,0.1]), default=0.05, label='First Propagation Significance'),
    Field('kde_probability',requires=IS_IN_SET(KDE_PROBABILITY_CHOICES,zero=None),default='0.85',label='KDE probability'),
    Field('zscore', 'double', requires=IS_IN_SET([1.04,1.28,1.64,2.33]), default=1.64, label='Zscore Semantic Similarity'),
    Field('second_propagation_damping', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='Second Propagation Damping'),
    Field('minimum_ego_nodes', 'double', requires=IS_IN_SET([i for i in range(1, 10, 1)]), default=5, label='Minimum Ego Nodes'),
    Field('third_propagation_damping', 'double', requires=IS_IN_SET([0.3,0.4,0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.95]), default=0.85, label='Third Propagation Damping'),
    Field('fisher_significance', 'double', requires=IS_IN_SET([0.01,0.05,0.1]), default=0.05, label='Fisher Significance'),
    migrate=True
)

db.commit()
